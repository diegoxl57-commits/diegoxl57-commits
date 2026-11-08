"""Narração com a ElevenLabs, com o tempo de cada palavra para as legendas."""
import base64
import subprocess
from pathlib import Path

import requests

URL_TTS = "https://api.elevenlabs.io/v1/text-to-speech/{voz}/with-timestamps"


class ErroNarracao(RuntimeError):
    pass


def narrar(cfg: dict, texto: str, destino: Path, api_key: str) -> tuple[Path, list[dict]]:
    n = cfg["narracao"]
    corpo = {
        "text": texto,
        "model_id": n.get("modelo", "eleven_multilingual_v2"),
        "voice_settings": {
            "stability": n.get("estabilidade", 0.45),
            "similarity_boost": n.get("similaridade", 0.8),
            "style": n.get("estilo", 0.15),
            "use_speaker_boost": True,
            "speed": n.get("velocidade", 1.0),
        },
    }
    resp = requests.post(
        URL_TTS.format(voz=n["voice_id"]),
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json=corpo,
        timeout=120,
    )
    if resp.status_code == 401:
        raise ErroNarracao("Chave da ElevenLabs recusada (401). Confira o secret ELEVENLABS_API_KEY.")
    if resp.status_code >= 400:
        raise ErroNarracao(f"Erro {resp.status_code} na ElevenLabs: {resp.text[:300]}")
    dados = resp.json()

    audio = destino / "narracao.mp3"
    audio.write_bytes(base64.b64decode(dados["audio_base64"]))
    alinhamento = dados.get("alignment") or dados.get("normalized_alignment")
    if not alinhamento:
        raise ErroNarracao("A ElevenLabs não devolveu o tempo das palavras.")
    return audio, palavras_do_alinhamento(alinhamento)


def palavras_do_alinhamento(al: dict) -> list[dict]:
    palavras, atual, inicio, fim = [], "", None, None
    for ch, t0, t1 in zip(
        al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    ):
        if ch.isspace():
            if atual:
                palavras.append({"texto": atual, "inicio": inicio, "fim": fim})
            atual, inicio = "", None
            continue
        if not atual:
            inicio = t0
        atual += ch
        fim = t1
    if atual:
        palavras.append({"texto": atual, "inicio": inicio, "fim": fim})
    return palavras


def narracao_simulada(texto: str, destino: Path, palavras_por_segundo: float = 2.6) -> tuple[Path, list[dict]]:
    """Áudio mudo com tempos estimados. Só para testar o visual sem gastar créditos."""
    tokens = texto.split()
    passo = 1 / palavras_por_segundo
    palavras = [
        {"texto": t, "inicio": round(i * passo, 3), "fim": round((i + 0.9) * passo, 3)}
        for i, t in enumerate(tokens)
    ]
    duracao = len(tokens) * passo + 0.5
    audio = destino / "narracao.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", f"{duracao:.2f}", "-c:a", "libmp3lame", "-b:a", "128k", str(audio)],
        check=True,
    )
    return audio, palavras
