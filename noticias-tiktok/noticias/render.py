"""Montagem final com FFmpeg: fundo, manchete, barra de progresso, legendas e áudio."""
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


def _tempo_ass(s: float) -> str:
    s = max(0.0, s)
    h, resto = divmod(s, 3600)
    m, seg = divmod(resto, 60)
    return f"{int(h)}:{int(m):02d}:{seg:05.2f}"


def _cor_ass(hexa: str) -> str:
    hexa = hexa.lstrip("#")
    r, g, b = hexa[0:2], hexa[2:4], hexa[4:6]
    return f"&H00{b}{g}{r}".upper()


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


def legendas_ass(cfg: dict, palavras: list[dict], destino: Path) -> Path:
    v = cfg["video"]
    W, H = v["largura"], v["altura"]
    destaque = _cor_ass(v.get("cor_destaque", "#FFD400"))
    margem_inferior = H - 1250  # texto termina em y=1250, acima da área de botões do TikTok
    linhas = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {W}",
        f"PlayResY: {H}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Legenda,Montserrat Black,100,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,"
        f"0,0,0,0,100,100,0,0,1,8,4,2,60,120,{margem_inferior},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    grupos = agrupar(palavras)
    for gi, grupo in enumerate(grupos):
        proximo_inicio = grupos[gi + 1][0]["inicio"] if gi + 1 < len(grupos) else None
        for i, p in enumerate(grupo):
            inicio = p["inicio"]
            if i + 1 < len(grupo):
                fim = grupo[i + 1]["inicio"]
            else:
                fim = p["fim"] + 0.3
                if proximo_inicio is not None:
                    fim = min(fim, proximo_inicio)
            if fim <= inicio:
                fim = inicio + 0.08
            partes = []
            for j, q in enumerate(grupo):
                t = q["texto"].upper().replace("{", "(").replace("}", ")")
                if j == i:
                    partes.append(f"{{\\c{destaque}&\\fscx108\\fscy108}}{t}{{\\r}}")
                else:
                    partes.append(t)
            linhas.append(
                f"Dialogue: 0,{_tempo_ass(inicio)},{_tempo_ass(fim)},Legenda,,0,0,0,,{' '.join(partes)}"
            )
    caminho = destino / "legendas.ass"
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return caminho


def montar(cfg: dict, destino: Path, audio: Path, legendas: Path, manchete: Path,
           fundos: list[Path], fundo_alternativo: Path | None) -> Path:
    v = cfg["video"]
    W, H, fps = v["largura"], v["altura"], v["fps"]
    total = duracao(audio) + 0.8
    cor_barra = "0x" + v.get("cor_marca", "#E1251B").lstrip("#")

    entradas, filtros = [], []
    if fundos:
        seg = total / len(fundos)
        for i, f in enumerate(fundos):
            entradas += ["-stream_loop", "-1", "-t", f"{seg + 0.5:.3f}", "-i", str(f)]
            filtros.append(
                f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
                f"fps={fps},trim=duration={seg:.3f},setpts=PTS-STARTPTS,eq=saturation=0.9[c{i}]"
            )
        filtros.append("".join(f"[c{i}]" for i in range(len(fundos))) + f"concat=n={len(fundos)}:v=1:a=0[bg]")
        n = len(fundos)
    else:
        entradas += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(fundo_alternativo)]
        filtros.append(
            f"[0:v]crop={W}:{H}:x='(in_w-out_w)/2+50*sin(t/4)':y='(in_h-out_h)/2+80*sin(t/6)',"
            f"setsar=1,fps={fps}[bg]"
        )
        n = 1

    entradas += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(manchete)]
    i_manchete = n
    entradas += ["-i", str(audio)]
    i_audio = n + 1
    musica = v.get("musica_fundo")
    if musica:
        entradas += ["-stream_loop", "-1", "-i", str(musica)]

    filtros += [
        f"[bg][{i_manchete}:v]overlay=0:0:format=auto[v1]",
        f"color=c={cor_barra}:s={W}x12:d={total:.3f}:r={fps}[barra]",
        f"[v1][barra]overlay=x='-w+w*t/{total:.3f}':y=0[v2]",
        f"[v2]ass={legendas.name}:fontsdir='{FONTES}',format=yuv420p[v]",
        f"[{i_audio}:a]aresample=44100,apad=pad_dur=0.8[voz]",
    ]
    if musica:
        vol = float(v.get("volume_musica", 0.08))
        filtros += [
            f"[{i_audio + 1}:a]aresample=44100,volume={vol},afade=t=out:st={total - 1.5:.3f}:d=1.5[mus]",
            "[voz][mus]amix=inputs=2:duration=first:normalize=0[a]",
        ]
    else:
        filtros.append("[voz]anull[a]")

    saida = destino / "video.mp4"
    comando = [
        "ffmpeg", "-y", "-loglevel", "error", *entradas,
        "-filter_complex", ";".join(filtros),
        "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-profile:v", "high", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(saida),
    ]
    subprocess.run(comando, check=True, cwd=destino)
    return saida
