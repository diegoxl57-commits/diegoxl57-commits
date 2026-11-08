"""Imagens do vídeo: vídeos de fundo (Pexels), vinheta, faixa do topo e fundo alternativo."""
import textwrap
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import FONTES

URL_PEXELS = "https://api.pexels.com/videos/search"


def cor(hexa: str) -> tuple[int, int, int]:
    hexa = hexa.lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))


def fonte(nome: str, tamanho: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTES / f"Montserrat-{nome}.ttf"), tamanho)


# ---------------------------------------------------------------- Pexels
def baixar_fundos(termos: list[str], quantidade: int, destino: Path, api_key: str | None) -> list[dict]:
    """Baixa vídeos verticais livres de direitos, variando entre os termos do roteiro."""
    if not api_key or quantidade <= 0:
        return []
    candidatos: list[list[dict]] = []
    for termo in termos:
        try:
            resp = requests.get(
                URL_PEXELS,
                params={"query": termo, "orientation": "portrait", "size": "medium", "per_page": 8},
                headers={"Authorization": api_key},
                timeout=30,
            )
            resp.raise_for_status()
            candidatos.append(resp.json().get("videos", []))
        except requests.RequestException as e:
            print(f"[pexels] busca '{termo}' falhou: {e}")

    escolhidos, vistos, rodada = [], set(), 0
    while len(escolhidos) < quantidade and any(len(c) > rodada for c in candidatos):
        for lista in candidatos:
            if len(escolhidos) >= quantidade or len(lista) <= rodada:
                continue
            v = lista[rodada]
            arquivo = _melhor_arquivo(v.get("video_files", []))
            if v["id"] in vistos or v.get("duration", 0) < 3 or not arquivo:
                continue
            vistos.add(v["id"])
            caminho = destino / f"fundo_{len(escolhidos)}.mp4"
            try:
                with requests.get(arquivo["link"], stream=True, timeout=120) as r:
                    r.raise_for_status()
                    with open(caminho, "wb") as f:
                        for bloco in r.iter_content(1 << 20):
                            f.write(bloco)
            except requests.RequestException as e:
                print(f"[pexels] download falhou: {e}")
                continue
            escolhidos.append({"arquivo": caminho, "autor": v.get("user", {}).get("name"), "url": v.get("url")})
        rodada += 1
    return escolhidos


def _melhor_arquivo(arquivos: list[dict]) -> dict | None:
    verticais = [
        a for a in arquivos
        if a.get("file_type") == "video/mp4" and a.get("height") and a.get("width")
        and a["height"] > a["width"] and a["height"] >= 1280
    ]
    if not verticais:
        return None
    return min(verticais, key=lambda a: abs(a["height"] - 1920))


# ---------------------------------------------------------------- fundo alternativo
def fundo_gerado(cfg: dict, destino: Path) -> Path:
    """Fundo escuro com brilho na cor da marca, usado quando não há vídeo de banco."""
    v = cfg["video"]
    W, H = int(v["largura"] * 1.2), int(v["altura"] * 1.2)
    img = Image.new("RGB", (W, H), (10, 12, 18))
    brilho = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(brilho)
    d.ellipse([-W * 0.3, H * 0.05, W * 0.8, H * 0.55], fill=cor(v.get("cor_marca", "#E1251B")))
    d.ellipse([W * 0.35, H * 0.5, W * 1.3, H * 1.05], fill=(30, 60, 140))
    brilho = brilho.filter(ImageFilter.GaussianBlur(220))
    img = Image.blend(img, brilho, 0.55)
    caminho = destino / "fundo_gerado.png"
    img.save(caminho)
    return caminho


# ---------------------------------------------------------------- camadas fixas
def vinheta(cfg: dict, destino: Path) -> Path:
    """Escurece topo e base para o texto ser legível sobre qualquer vídeo."""
    W, H = cfg["video"]["largura"], cfg["video"]["altura"]
    grad = Image.new("L", (1, H))
    for y in range(H):
        if y < 620:
            a = int(190 * (1 - y / 620) ** 1.3)
        elif y > 1150:
            a = int(150 * ((y - 1150) / (H - 1150)) ** 1.1)
        else:
            a = 0
        grad.putpixel((0, y), a)
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    camada.putalpha(grad.resize((W, H)))
    caminho = destino / "vinheta.png"
    camada.save(caminho)
    return caminho


def faixa_topo(cfg: dict, pauta: dict, destino: Path) -> Path:
    """Selo do canal, título curto, fontes e aviso de IA. Entra depois do gancho."""
    v = cfg["video"]
    W, H = v["largura"], v["altura"]
    marca = cor(v.get("cor_marca", "#E1251B"))
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    margem, y = 60, 120

    f_selo = fonte("Black", 32)
    nome = cfg["canal"]["nome"].upper()
    cx = d.textbbox((0, 0), nome, font=f_selo)
    w_selo, h_selo = cx[2] - cx[0] + 36, cx[3] - cx[1] + 24
    d.rounded_rectangle([margem, y, margem + w_selo, y + h_selo], radius=10, fill=marca + (255,))
    d.text((margem + 18, y + 12 - cx[1]), nome, font=f_selo, fill="white")
    agora = datetime.now(ZoneInfo(cfg["canal"].get("fuso_horario", "America/Sao_Paulo")))
    d.text((margem + w_selo + 20, y + (h_selo - 30) // 2 - 2), agora.strftime("%d/%m/%Y"),
           font=fonte("SemiBold", 30), fill=(235, 235, 235))
    y += h_selo + 22

    f_tit = fonte("ExtraBold", 50)
    for linha in textwrap.wrap(pauta["titulo_tela"], width=30)[:2]:
        d.text((margem, y), linha, font=f_tit, fill="white", stroke_width=3, stroke_fill=(0, 0, 0))
        y += 62
    y += 8
    f_info = fonte("SemiBold", 28)
    partes = []
    if pauta.get("fontes"):
        partes.append("Fontes: " + " · ".join(pauta["fontes"][:3]))
    if v.get("mostrar_selo_ia", True):
        partes.append("Narração gerada por IA")
    if partes:
        d.text((margem, y), "  |  ".join(partes), font=f_info, fill=(220, 220, 220),
               stroke_width=2, stroke_fill=(0, 0, 0))

    caminho = destino / "topo.png"
    camada.save(caminho)
    return caminho
