"""Montagem no formato viral com FFmpeg.

Linha do tempo:
  0s ──── gancho gigante na tela (primeira frase) + impacto sonoro
  ~2s ─── faixa do topo entra; legendas palavra por palavra; cortes de cena com zoom e "whoosh"
  fim ─── pergunta para comentários com selo "COMENTE" + sino
"""
import random
import re
import subprocess
from pathlib import Path

from .config import FONTES

FINAIS = (".", "!", "?", ":", ";")


def duracao(arquivo: Path) -> float:
    saida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arquivo)],
        capture_output=True, text=True, check=True,
    )
    return float(saida.stdout.strip())


def _ffmpeg(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True, cwd=cwd)


def _tempo_ass(s: float) -> str:
    s = max(0.0, s)
    h, resto = divmod(s, 3600)
    m, seg = divmod(resto, 60)
    return f"{int(h)}:{int(m):02d}:{seg:05.2f}"


def _cor_ass(hexa: str) -> str:
    hexa = hexa.lstrip("#")
    return f"&H00{hexa[4:6]}{hexa[2:4]}{hexa[0:2]}".upper()


def _normal(palavra: str) -> str:
    return re.sub(r"[^\wÀ-ÿ%]", "", palavra.lower())


# ---------------------------------------------------------------- marcos da narração
def marcos(palavras: list[dict], pergunta: str) -> tuple[float, float | None]:
    """Fim do gancho (primeira frase) e início da pergunta final."""
    fim_gancho = palavras[min(len(palavras), 14) - 1]["fim"]
    for p in palavras[:14]:
        if p["texto"].endswith(FINAIS):
            fim_gancho = p["fim"]
            break
    fim_gancho = max(1.4, min(fim_gancho, 3.8))

    inicio_pergunta = None
    alvo = [_normal(w) for w in pergunta.split()][:3]
    if alvo:
        normais = [_normal(p["texto"]) for p in palavras]
        for i in range(len(normais) - len(alvo), -1, -1):
            if normais[i:i + len(alvo)] == alvo:
                inicio_pergunta = palavras[i]["inicio"]
                break
    return fim_gancho, inicio_pergunta


def agrupar(palavras: list[dict], max_palavras: int = 3, max_chars: int = 14) -> list[list[dict]]:
    grupos, atual = [], []
    for p in palavras:
        tamanho = sum(len(x["texto"]) + 1 for x in atual) + len(p["texto"])
        if atual and (len(atual) >= max_palavras or tamanho > max_chars):
            grupos.append(atual)
            atual = []
        atual.append(p)
        if p["texto"].endswith(FINAIS):
            grupos.append(atual)
            atual = []
    if atual:
        grupos.append(atual)
    return grupos


# ---------------------------------------------------------------- legendas (ASS)
def legendas_ass(cfg: dict, pauta: dict, palavras: list[dict], fim_gancho: float,
                 inicio_pergunta: float | None, total: float, destino: Path) -> Path:
    v = cfg["video"]
    W, H = v["largura"], v["altura"]
    ativa = _cor_ass(v.get("cor_destaque", "#FFD400"))
    chave = _cor_ass(v.get("cor_chave", "#3DFF8B"))
    marca = _cor_ass(v.get("cor_marca", "#E1251B"))
    destaques = {_normal(p) for p in pauta.get("palavras_destaque", [])}
    estilo = "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, " \
             "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, " \
             "Alignment, MarginL, MarginR, MarginV, Encoding"
    linhas = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]", estilo,
        "Style: Legenda,Montserrat Black,104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,"
        "0,0,0,0,100,100,0,0,1,8,4,5,60,130,0,1",
        f"Style: Gancho,Montserrat Black,122,&H00FFFFFF,&H00FFFFFF,{marca},&H00000000,"
        "0,0,0,0,100,100,0,0,3,22,0,5,90,90,0,1",
        f"Style: Selo,Montserrat Black,70,&H00FFFFFF,&H00FFFFFF,{marca},&H00000000,"
        "0,0,0,0,100,100,2,0,3,14,0,5,60,60,0,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    def evento(ini: float, fim: float, estilo_: str, texto: str, camada: int = 0) -> None:
        linhas.append(f"Dialogue: {camada},{_tempo_ass(ini)},{_tempo_ass(fim)},{estilo_},,0,0,0,,{texto}")

    # gancho gigante com efeito de "pulo"
    gancho = pauta.get("gancho_tela", "").upper().replace("{", "(").replace("}", ")")
    if gancho:
        evento(0, fim_gancho, "Gancho",
               "{\\pos(540,880)\\frz-2\\fscx60\\fscy60\\t(0,150,\\fscx110\\fscy110)\\t(150,240,\\fscx100\\fscy100)}"
               + gancho, camada=2)

    # legendas palavra por palavra depois do gancho
    corpo = [p for p in palavras if p["inicio"] >= fim_gancho - 0.05]
    grupos = agrupar(corpo)
    for gi, grupo in enumerate(grupos):
        proximo = grupos[gi + 1][0]["inicio"] if gi + 1 < len(grupos) else None
        for i, p in enumerate(grupo):
            ini = p["inicio"]
            fim = grupo[i + 1]["inicio"] if i + 1 < len(grupo) else p["fim"] + 0.3
            if proximo is not None and i + 1 == len(grupo):
                fim = min(fim, proximo)
            fim = max(fim, ini + 0.08)
            partes = []
            for j, q in enumerate(grupo):
                t = q["texto"].upper().replace("{", "(").replace("}", ")")
                if j == i:
                    partes.append(f"{{\\c{ativa}&\\fscx112\\fscy112}}{t}{{\\r}}")
                elif _normal(q["texto"]) in destaques:
                    partes.append(f"{{\\c{chave}&}}{t}{{\\r}}")
                else:
                    partes.append(t)
            pulo = "\\fscx80\\fscy80\\t(0,90,\\fscx100\\fscy100)" if i == 0 else ""
            evento(ini, fim, "Legenda", f"{{\\pos(500,1060){pulo}}}" + " ".join(partes), camada=1)

    # selo de comentário durante a pergunta final
    if inicio_pergunta is not None:
        evento(inicio_pergunta, total, "Selo",
               "{\\pos(500,880)\\fscx70\\fscy70\\t(0,140,\\fscx100\\fscy100)}COMENTE AQUI", camada=2)

    caminho = destino / "legendas.ass"
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return caminho


# ---------------------------------------------------------------- cenas de fundo
def cortes(total: float, intervalo: float, semente: int) -> list[float]:
    rng = random.Random(semente)
    pontos, t = [0.0], 0.0
    while True:
        t += intervalo * rng.uniform(0.85, 1.15)
        if t >= total - 1.0:
            break
        pontos.append(round(t, 3))
    return pontos


def montar_fundo(cfg: dict, destino: Path, pontos: list[float], total: float,
                 clipes: list[Path], imagem: Path | None) -> Path:
    v = cfg["video"]
    W, H, fps = v["largura"], v["altura"], v["fps"]
    lista = []
    for k, ini in enumerate(pontos):
        fim = pontos[k + 1] if k + 1 < len(pontos) else total
        dur = fim - ini
        quadros = max(1, round(dur * fps))
        z0, z1 = (1.0, 1.12) if k % 2 == 0 else (1.12, 1.0)
        zoom = (f"zoompan=z='{z0}+({z1 - z0})*on/{quadros}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":s={W}x{H}:fps={fps}")
        cobrir = f"scale={int(W * 1.5)}:{int(H * 1.5)}:force_original_aspect_ratio=increase,crop={int(W * 1.5)}:{int(H * 1.5)}"
        if clipes:
            clipe = clipes[k % len(clipes)]
            desloc = (k // len(clipes)) * 2.5  # reaproveita o clipe a partir de outro trecho
            entrada = ["-stream_loop", "-1", "-ss", f"{desloc:.2f}", "-t", f"{dur + 0.2:.3f}", "-i", str(clipe)]
            filtro = f"fps={fps},{cobrir},{zoom},eq=saturation=1.08:contrast=1.04,setsar=1,trim=duration={dur:.3f}"
        else:
            entrada = ["-loop", "1", "-t", f"{dur + 0.2:.3f}", "-i", str(imagem)]
            filtro = f"fps={fps},{cobrir},{zoom},setsar=1,trim=duration={dur:.3f}"
        cena = destino / f"cena_{k:02d}.mp4"
        _ffmpeg(*entrada, "-vf", filtro, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-pix_fmt", "yuv420p", str(cena))
        lista.append(f"file '{cena.name}'")
    (destino / "cenas.txt").write_text("\n".join(lista) + "\n", encoding="utf-8")
    fundo = destino / "fundo.mp4"
    _ffmpeg("-f", "concat", "-safe", "0", "-i", "cenas.txt", "-c", "copy", fundo.name, cwd=destino)
    return fundo


# ---------------------------------------------------------------- montagem final
def montar(cfg: dict, destino: Path, fundo: Path, pontos: list[float], total: float, fim_gancho: float,
           voz: Path, trilha: Path | None, efeitos: Path, vinheta: Path, topo: Path, legendas: Path) -> Path:
    v = cfg["video"]
    W, fps = v["largura"], v["fps"]
    cor_barra = "0x" + v.get("cor_marca", "#E1251B").lstrip("#")
    flashes = "+".join(f"between(t,{c:.3f},{c + 0.06:.3f})" for c in pontos[1:]) or "0"

    entradas = ["-i", str(fundo),
                "-loop", "1", "-t", f"{total:.3f}", "-i", str(vinheta),
                "-loop", "1", "-t", f"{total:.3f}", "-i", str(topo),
                "-i", str(voz), "-i", str(efeitos)]
    if trilha:
        entradas += ["-stream_loop", "-1", "-i", str(trilha)]

    filtros = [
        f"[0:v]drawbox=x=0:y=0:w=iw:h=ih:color=white@0.28:t=fill:enable='{flashes}'[b0]",
        "[b0][1:v]overlay=0:0:format=auto[b1]",
        f"[b1][2:v]overlay=0:0:format=auto:enable='gte(t,{fim_gancho:.3f})'[b2]",
        f"color=c={cor_barra}:s={W}x12:d={total:.3f}:r={fps}[barra]",
        f"[b2][barra]overlay=x='-w+w*t/{total:.3f}':y=0[b3]",
        f"[b3]ass={legendas.name}:fontsdir='{FONTES}',format=yuv420p[v]",
        "[3:a]aresample=44100,apad=pad_dur=1,asplit=2[voz][chave]",
        f"[4:a]aresample=44100,volume={float(v.get('volume_efeitos', 0.55))}[sfx]",
    ]
    if trilha:
        filtros += [
            f"[5:a]aresample=44100,volume={float(v.get('volume_musica', 0.16))}[mus]",
            "[mus][chave]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=350[musd]",
            "[voz][musd][sfx]amix=inputs=3:duration=first:normalize=0[mix]",
        ]
    else:
        filtros += ["[chave]anullsink", "[voz][sfx]amix=inputs=2:duration=first:normalize=0[mix]"]
    filtros.append("[mix]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[a]")

    saida = destino / "video.mp4"
    _ffmpeg(*entradas, "-filter_complex", ";".join(filtros),
            "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-profile:v", "high", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", saida.name, cwd=destino)
    return saida
