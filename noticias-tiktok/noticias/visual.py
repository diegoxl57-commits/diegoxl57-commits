"""Imagens do vídeo: vídeos de fundo (Pexels), manchete e fundo alternativo."""
import textwrap
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import FONTES

URL_PEXELS = "https://api.pexels.com/videos/search"


def _cor(hexa: str) -> tuple[int, int, int]:
    hexa = hexa.lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))


def _fonte(nome: str, tamanho: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTES / f"Montserrat-{nome}.ttf"), tamanho)


# ---------------------------------------------------------------- Pexels
def baixar_fundos(palavras: list[str], quantidade: int, destino: Path, api_key: str | None) -> list[dict]:
    """Baixa vídeos verticais livres de direitos. Sem chave ou sem resultado, devolve lista vazia."""
    if not api_key or quantidade <= 0:
        return []
    escolhidos, vistos = [], set()
    for termo in palavras:
        if len(escolhidos) >= quantidade:
            break
        try:
            resp = requests.get(
                URL_PEXELS,
                params={"query": termo, "orientation": "portrait", "size": "medium", "per_page": 6},
                headers={"Authorization": api_key},
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[pexels] busca '{termo}' falhou: {e}")
            continue
        for v in resp.json().get("videos", []):
            if v["id"] in vistos or v.get("duration", 0) < 4:
                continue
            arquivo = _melhor_arquivo(v.get("video_files", []))
            if not arquivo:
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
            break  # um vídeo por termo, para variar as cenas
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
    W, H = int(v["largura"] * 1.12), int(v["altura"] * 1.12)
    img = Image.new("RGB", (W, H), (10, 12, 18))
    brilho = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(brilho)
    cor = _cor(v.get("cor_marca", "#E1251B"))
    d.ellipse([-W * 0.3, H * 0.05, W * 0.8, H * 0.55], fill=cor)
    d.ellipse([W * 0.35, H * 0.5, W * 1.3, H * 1.05], fill=(30, 60, 140))
    brilho = brilho.filter(ImageFilter.GaussianBlur(220))
    img = Image.blend(img, brilho, 0.55)
    caminho = destino / "fundo_gerado.png"
    img.save(caminho)
    return caminho


# ---------------------------------------------------------------- manchete
def camada_manchete(cfg: dict, pauta: dict, destino: Path) -> Path:
    v = cfg["video"]
    W, H = v["largura"], v["altura"]
    marca = _cor(v.get("cor_marca", "#E1251B"))
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # escurece topo e base para dar leitura sobre qualquer vídeo
    grad = Image.new("L", (1, H))
    for y in range(H):
        if y < 900:
            a = int(200 * (1 - y / 900) ** 1.4)
        elif y > 1300:
            a = int(170 * ((y - 1300) / (H - 1300)) ** 1.2)
        else:
            a = 0
        grad.putpixel((0, y), a)
    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    sombra.putalpha(grad.resize((W, H)))
    camada = Image.alpha_composite(camada, sombra)

    d = ImageDraw.Draw(camada)
    margem = 70
    y = 150

    # selo do canal + data
    f_selo = _fonte("Black", 38)
    nome = cfg["canal"]["nome"].upper()
    caixa = d.textbbox((0, 0), nome, font=f_selo)
    w_selo, h_selo = caixa[2] - caixa[0] + 44, caixa[3] - caixa[1] + 30
    d.rounded_rectangle([margem, y, margem + w_selo, y + h_selo], radius=12, fill=marca + (255,))
    d.text((margem + 22, y + 15 - caixa[1]), nome, font=f_selo, fill="white")
    agora = datetime.now(ZoneInfo(cfg["canal"].get("fuso_horario", "America/Sao_Paulo")))
    f_data = _fonte("SemiBold", 32)
    d.text((margem + w_selo + 24, y + (h_selo - 32) // 2 - 2), agora.strftime("%d/%m/%Y"), font=f_data, fill=(235, 235, 235))
    y += h_selo + 40

    # manchete: ajusta o tamanho para caber em até 4 linhas
    titulo = pauta["titulo_tela"].upper()
    for tamanho in (86, 78, 70, 62, 56):
        f_tit = _fonte("Black", tamanho)
        largura_char = d.textlength("M", font=f_tit) * 0.78
        linhas = textwrap.wrap(titulo, width=max(8, int((W - 2 * margem - 40) / largura_char)))
        if len(linhas) <= 4 and all(d.textlength(l, font=f_tit) <= W - 2 * margem - 40 for l in linhas):
            break
    altura_linha = int(tamanho * 1.12)
    painel_h = altura_linha * len(linhas) + 50
    painel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(painel).rounded_rectangle(
        [margem - 10, y, W - margem + 10, y + painel_h], radius=22, fill=(0, 0, 0, 165)
    )
    camada = Image.alpha_composite(camada, painel)
    d = ImageDraw.Draw(camada)
    d.rectangle([margem - 10, y, margem + 2, y + painel_h], fill=marca + (255,))
    ty = y + 25
    for linha in linhas:
        d.text((margem + 24, ty), linha, font=f_tit, fill="white")
        ty += altura_linha
    y += painel_h + 26

    # fontes e selo de IA
    f_info = _fonte("SemiBold", 30)
    fontes = " · ".join(pauta.get("fontes", [])[:4])
    if fontes:
        d.text((margem, y), f"Fontes: {fontes}", font=f_info, fill=(225, 225, 225))
        y += 44
    if v.get("mostrar_selo_ia", True):
        d.text((margem, y), "Narração gerada por IA", font=f_info, fill=(190, 190, 190))

    caminho = destino / "manchete.png"
    camada.save(caminho)
    return caminho
