"""Narração com o tempo de cada palavra (para as legendas).

Provedores:
  google      Google Cloud Text-to-Speech (grátis até 1 milhão de caracteres/mês nas vozes neurais)
  elevenlabs  ElevenLabs (pago)
"""
import base64
import html
import re
import subprocess
from pathlib import Path

import requests

from .config import segredo

URL_GOOGLE = "https://texttospeech.googleapis.com/v1beta1/text:synthesize"
URL_ELEVEN = "https://api.elevenlabs.io/v1/text-to-speech/{voz}/with-timestamps"


class ErroNarracao(RuntimeError):
    pass


def narrar(cfg: dict, texto: str, destino: Path) -> tuple[Path, list[dict]]:
    provedor = cfg["narracao"].get("provedor", "google")
    if provedor == "google":
        return narrar_google(cfg, texto, destino, segredo("GOOGLE_TTS_API_KEY"))
    if provedor == "elevenlabs":
        return narrar_elevenlabs(cfg, texto, destino, segredo("ELEVENLABS_API_KEY"))
    raise ErroNarracao(f"Provedor de voz desconhecido: {provedor}")


def chave_configurada(cfg: dict) -> bool:
    nome = {"google": "GOOGLE_TTS_API_KEY", "elevenlabs": "ELEVENLABS_API_KEY"}.get(
        cfg["narracao"].get("provedor", "google"), "")
    return bool(segredo(nome, obrigatorio=False)) if nome else False


# ---------------------------------------------------------------- Google
def narrar_google(cfg: dict, texto: str, destino: Path, api_key: str) -> tuple[Path, list[dict]]:
    g = cfg["narracao"].get("google", {})
    palavras = texto.split()
    # uma marca antes de cada palavra: o Google devolve o instante exato de cada uma
    ssml = "<speak>" + " ".join(f'<mark name="{i}"/>{html.escape(p)}' for i, p in enumerate(palavras)) + "</speak>"
    ultimo_erro = ""
    for voz in g.get("vozes", ["pt-BR-Neural2-B"]):
        corpo = {
            "input": {"ssml": ssml},
            "voice": {"languageCode": "pt-BR", "name": voz},
            "audioConfig": {
                "audioEncoding": "LINEAR16",  # WAV sem perda (o MP3 do Google sai em 32 kbps)
                "speakingRate": float(g.get("velocidade", 1.1)),
                "pitch": float(g.get("tom", 0.0)),
            },
            "enableTimePointing": ["SSML_MARK"],
        }
        resp = requests.post(URL_GOOGLE, params={"key": api_key}, json=corpo, timeout=120)
        if resp.status_code == 400 and "voice" in resp.text.lower():
            ultimo_erro = resp.text[:200]
            print(f"[narracao] Voz {voz} indisponível, tentando a próxima.")
            continue
        if resp.status_code == 403:
            raise ErroNarracao("Google recusou a chave (403). Ative a 'Cloud Text-to-Speech API' no projeto "
                               "e confira o faturamento e as restrições da chave GOOGLE_TTS_API_KEY.")
        if resp.status_code >= 400:
            raise ErroNarracao(f"Erro {resp.status_code} no Google Text-to-Speech: {resp.text[:300]}")
        dados = resp.json()
        audio = destino / "narracao.wav"
        audio.write_bytes(base64.b64decode(dados["audioContent"]))
        marcas = {int(t["markName"]): float(t.get("timeSeconds", 0)) for t in dados.get("timepoints", [])}
        print(f"[narracao] Google, voz {voz}.")
        return audio, _tempos_das_marcas(palavras, marcas, _duracao(audio))
    raise ErroNarracao(f"Nenhuma das vozes configuradas funcionou: {ultimo_erro}")


def _tempos_das_marcas(palavras: list[str], marcas: dict[int, float], duracao: float) -> list[dict]:
    if len(marcas) < len(palavras) * 0.8:
        print("[narracao] Sem tempos por palavra suficientes; estimando pelo tamanho das palavras.")
        return _tempos_estimados(palavras, duracao)
    inicios, anterior = [], 0.0
    for i in range(len(palavras)):
        anterior = marcas.get(i, anterior)
        inicios.append(anterior)
    resultado = []
    for i, p in enumerate(palavras):
        fim = inicios[i + 1] if i + 1 < len(palavras) else duracao - 0.1
        resultado.append({"texto": p, "inicio": round(inicios[i], 3), "fim": round(max(fim - 0.02, inicios[i] + 0.05), 3)})
    return resultado


def _tempos_estimados(palavras: list[str], duracao: float) -> list[dict]:
    pesos = [len(p) + 2 + (6 if re.search(r"[.!?]$", p) else 3 if re.search(r"[,;:]$", p) else 0) for p in palavras]
    escala = max(0.1, duracao - 0.2) / sum(pesos)
    t, resultado = 0.1, []
    for p, w in zip(palavras, pesos):
        resultado.append({"texto": p, "inicio": round(t, 3), "fim": round(t + w * escala * 0.85, 3)})
        t += w * escala
    return resultado


def _duracao(arquivo: Path) -> float:
    saida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arquivo)],
        capture_output=True, text=True, check=True,
    )
    return float(saida.stdout.strip())


# ---------------------------------------------------------------- ElevenLabs
def narrar_elevenlabs(cfg: dict, texto: str, destino: Path, api_key: str) -> tuple[Path, list[dict]]:
    n = cfg["narracao"].get("elevenlabs", {})
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
        URL_ELEVEN.format(voz=n["voice_id"]),
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


# ---------------------------------------------------------------- demonstração
def narracao_simulada(texto: str, destino: Path, palavras_por_segundo: float = 2.6) -> tuple[Path, list[dict]]:
    """Áudio mudo com tempos estimados. Só para testar o visual sem gastar nada."""
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
