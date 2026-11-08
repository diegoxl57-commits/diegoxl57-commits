"""Coleta gratuita: manchetes recentes dos feeds RSS/Atom dos próprios veículos."""
import hashlib
import html
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

TAGS_HTML = re.compile(r"<[^>]+>")
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "rss1": "http://purl.org/rss/1.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


class ErroRSS(RuntimeError):
    pass


# situação de cada feed na última coleta: {veiculo: "ok (N notícias)" | "erro: ..."}
SITUACAO: dict[str, str] = {}


def buscar_noticias(cfg: dict) -> list[dict]:
    coleta = cfg["coleta"]
    rss = coleta["rss"]
    corte = datetime.now(timezone.utc) - timedelta(hours=float(coleta.get("janela_horas", 8)))
    repo = os.environ.get("GITHUB_REPOSITORY", "robo-noticias")
    cabecalho = {"User-Agent": f"Mozilla/5.0 (compatible; robo-noticias/1.0; +https://github.com/{repo})"}

    noticias, falhas = [], []
    for veiculo, url in rss["feeds"].items():
        try:
            resp = requests.get(url, headers=cabecalho, timeout=20)
            resp.raise_for_status()
            itens = ler_feed(resp.content)
        except (requests.RequestException, ET.ParseError) as e:
            falhas.append(f"{veiculo} ({e.__class__.__name__})")
            SITUACAO[veiculo] = f"erro: {str(e)[:120]}"
            continue
        recentes = [i for i in itens if i["data"] and i["data"] >= corte]
        recentes.sort(key=lambda i: i["data"], reverse=True)
        usados = recentes[: int(rss.get("max_por_feed", 15))]
        for i in usados:
            noticias.append(_normalizar(veiculo, i))
        SITUACAO[veiculo] = f"ok ({len(itens)} no feed, {len(usados)} recentes)"

    if falhas:
        print(f"[rss] Feeds indisponíveis nesta rodada: {', '.join(falhas)}")
    veiculos_ok = {n["fonte_usuario"] for n in noticias}
    if len(veiculos_ok) < int(coleta.get("minimo_fontes", 2)):
        raise ErroRSS(f"Poucos veículos com notícias recentes ({len(veiculos_ok)}). Confira os feeds no config.yaml.")
    return noticias


ENTIDADE_SOLTA = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)")
CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
DECLARACAO = re.compile(rb"<\?xml[^>]*encoding=[\"']([\w.-]+)[\"']", re.I)


def _xml_tolerante(conteudo: bytes) -> ET.Element:
    """Alguns feeds trazem '&' solto, entidades de HTML ou caracteres de controle; corrige e tenta de novo."""
    try:
        return ET.fromstring(conteudo)
    except ET.ParseError:
        m = DECLARACAO.search(conteudo[:200])
        texto = conteudo.decode(m.group(1).decode() if m else "utf-8", errors="replace")
        texto = re.sub(r"<\?xml[^>]*\?>", "", texto, count=1)
        texto = CONTROLE.sub("", ENTIDADE_SOLTA.sub("&amp;", texto))
        return ET.fromstring(texto)


def ler_feed(conteudo: bytes) -> list[dict]:
    raiz = _xml_tolerante(conteudo)
    itens = []
    # RSS 2.0
    for it in raiz.iter("item"):
        itens.append({
            "titulo": _texto(it, "title"),
            "link": _texto(it, "link") or _texto(it, "guid"),
            "resumo": _texto(it, "description"),
            "data": _data(_texto(it, "pubDate") or _texto(it, "dc:date")),
        })
    # RSS 1.0 (RDF)
    for it in raiz.iter(f"{{{NS['rss1']}}}item"):
        itens.append({
            "titulo": _texto(it, "rss1:title"),
            "link": _texto(it, "rss1:link"),
            "resumo": _texto(it, "rss1:description"),
            "data": _data(_texto(it, "dc:date")),
        })
    # Atom
    for it in raiz.iter(f"{{{NS['atom']}}}entry"):
        link = it.find("atom:link", NS)
        itens.append({
            "titulo": _texto(it, "atom:title"),
            "link": link.get("href") if link is not None else "",
            "resumo": _texto(it, "atom:summary") or _texto(it, "atom:content"),
            "data": _data(_texto(it, "atom:published") or _texto(it, "atom:updated")),
        })
    return [i for i in itens if i["titulo"] and i["link"]]


def _texto(no: ET.Element, caminho: str) -> str:
    el = no.find(caminho, NS)
    return (el.text or "").strip() if el is not None else ""


def _data(valor: str) -> datetime | None:
    if not valor:
        return None
    try:
        d = parsedate_to_datetime(valor)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _limpar(texto: str, limite: int = 300) -> str:
    texto = html.unescape(TAGS_HTML.sub(" ", html.unescape(texto or "")))
    texto = " ".join(texto.split())
    return texto[:limite]


def _normalizar(veiculo: str, item: dict) -> dict:
    titulo, resumo = _limpar(item["titulo"], 200), _limpar(item["resumo"])
    texto = titulo if not resumo or resumo.startswith(titulo) else f"{titulo} — {resumo}"
    return {
        "id": hashlib.sha1(item["link"].encode()).hexdigest()[:16],
        "fonte_usuario": veiculo,
        "fonte_nome": veiculo,
        "texto": texto,
        "criado_em": item["data"].isoformat(timespec="minutes"),
        "link_post": item["link"],
        "link_materia": item["link"],
    }
