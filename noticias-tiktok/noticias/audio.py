"""Trilha e efeitos sonoros gerados por código: originais e livres de direitos.

Se houver arquivos em assets/musicas/ (MP3/WAV com licença de uso), eles são usados
no lugar da trilha gerada.
"""
import random
import wave
from pathlib import Path

import numpy as np

from .config import RAIZ

TAXA = 44100
PASTA_MUSICAS = RAIZ / "assets" / "musicas"

# progressões em lá menor / ré menor (graus em semitons a partir da tônica)
PROGRESSOES = {
    "pulsante": [[0, 3, 7], [-4, 0, 3], [3, 7, 10], [-2, 2, 5]],   # i – VI – III – VII
    "tensa": [[0, 3, 7], [0, 3, 8], [-2, 1, 5], [-1, 3, 7]],
}


def _salvar(caminho: Path, estereo: np.ndarray) -> Path:
    dados = np.clip(estereo, -1, 1)
    pcm = (dados * 32767).astype("<i2")
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(pcm.tobytes())
    return caminho


def _passa_baixa(x: np.ndarray, corte: float | np.ndarray) -> np.ndarray:
    """Filtro de um polo; aceita frequência de corte variável no tempo."""
    corte = np.broadcast_to(np.asarray(corte, dtype=float), x.shape)
    a = 1 - np.exp(-2 * np.pi * corte / TAXA)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def _freq(semitom: float, base: float = 220.0) -> float:
    return base * 2 ** (semitom / 12)


def musica_externa() -> Path | None:
    if PASTA_MUSICAS.exists():
        faixas = [p for p in PASTA_MUSICAS.iterdir() if p.suffix.lower() in (".mp3", ".wav", ".m4a")]
        if faixas:
            return random.choice(faixas)
    return None


def gerar_trilha(estilo: str, duracao: float, destino: Path, semente: int = 0) -> Path | None:
    if estilo == "sem":
        return None
    externa = musica_externa()
    if externa:
        return externa
    rng = np.random.default_rng(semente)
    bpm = rng.choice([96, 100, 104, 110]) if estilo == "pulsante" else rng.choice([84, 90])
    n = int((duracao + 1) * TAXA)
    t = np.arange(n) / TAXA
    batida = 60 / bpm
    compasso = 4 * batida
    prog = PROGRESSOES.get(estilo, PROGRESSOES["pulsante"])
    tonica = rng.choice([-5, -3, 0])  # mi, fá#, lá

    # pad: senoides levemente desafinadas, ataque lento, troca de acorde a cada compasso
    pad = np.zeros(n)
    for c in range(int(duracao / compasso) + 2):
        ini, fim = int(c * compasso * TAXA), int((c + 1) * compasso * TAXA)
        if ini >= n:
            break
        fim = min(fim, n)
        tt = t[ini:fim] - t[ini]
        env = np.minimum(1, tt / 0.6) * np.minimum(1, (compasso - tt) / 0.4)
        for grau in prog[c % len(prog)]:
            f = _freq(grau + tonica)
            for desaf in (-0.15, 0.15):
                pad[ini:fim] += env * np.sin(2 * np.pi * f * (1 + desaf / 100) * tt) * 0.12
        # baixo: tônica do acorde uma oitava abaixo, em colcheias
        fb = _freq(prog[c % len(prog)][0] + tonica, 110.0)
        pulso = (tt % (batida / 2)) / (batida / 2)
        pad[ini:fim] += np.sin(2 * np.pi * fb * tt) * np.exp(-pulso * 4) * 0.22

    # bumbo suave nos tempos, chimbal nas colcheias (só no estilo pulsante)
    perc = np.zeros(n)
    if estilo == "pulsante":
        kick_t = np.arange(int(0.25 * TAXA)) / TAXA
        kick = np.sin(2 * np.pi * (45 + 60 * np.exp(-kick_t * 30)) * kick_t) * np.exp(-kick_t * 14) * 0.55
        hat_t = np.arange(int(0.04 * TAXA)) / TAXA
        ruido = rng.standard_normal(len(hat_t))
        hat = np.diff(ruido, prepend=0) * np.exp(-hat_t * 90) * 0.05
        b = 0.0
        while b < duracao + 1:
            i = int(b * TAXA)
            perc[i:i + len(kick)] += kick[: max(0, min(len(kick), n - i))]
            j = int((b + batida / 2) * TAXA)
            perc[j:j + len(hat)] += hat[: max(0, min(len(hat), n - j))]
            b += batida
    else:
        # tique-taque discreto, clima de "plantão"
        tic_t = np.arange(int(0.03 * TAXA)) / TAXA
        tic = np.sin(2 * np.pi * 1800 * tic_t) * np.exp(-tic_t * 160) * 0.06
        b = 0.0
        while b < duracao + 1:
            i = int(b * TAXA)
            perc[i:i + len(tic)] += tic[: max(0, min(len(tic), n - i))]
            b += batida

    mix = _passa_baixa(pad, 2400) + perc
    mix *= np.minimum(1, t / 1.0) * np.minimum(1, (duracao + 1 - t) / 1.5).clip(0, 1)
    mix /= max(1e-9, np.abs(mix).max()) / 0.6
    lfo = 0.1 * np.sin(2 * np.pi * t / 7)
    estereo = np.stack([mix * (1 - lfo), mix * (1 + lfo)], axis=1)
    return _salvar(destino / "trilha.wav", estereo)


def _whoosh(dur: float, rng) -> np.ndarray:
    n = int(dur * TAXA)
    t = np.arange(n) / TAXA
    env = np.sin(np.pi * t / dur) ** 2
    corte = 300 + 5200 * np.sin(np.pi * t / dur) ** 1.5
    return _passa_baixa(rng.standard_normal(n), corte) * env * 0.9


def _impacto() -> np.ndarray:
    t = np.arange(int(0.45 * TAXA)) / TAXA
    grave = np.sin(2 * np.pi * (38 + 90 * np.exp(-t * 18)) * t) * np.exp(-t * 7)
    return grave * 0.8


def _sino() -> np.ndarray:
    t = np.arange(int(0.8 * TAXA)) / TAXA
    return (np.sin(2 * np.pi * 1318.5 * t) + 0.5 * np.sin(2 * np.pi * 1975.5 * t)) * np.exp(-t * 6) * 0.25


def gerar_efeitos(duracao: float, cortes: list[float], inicio_pergunta: float | None,
                  destino: Path, semente: int = 0) -> Path:
    rng = np.random.default_rng(semente + 1)
    n = int((duracao + 1) * TAXA)
    trilha = np.zeros(n)

    def colocar(som: np.ndarray, quando: float, volume: float) -> None:
        i = max(0, int(quando * TAXA))
        fim = min(n, i + len(som))
        if fim > i:
            trilha[i:fim] += som[: fim - i] * volume

    colocar(_impacto(), 0.0, 0.9)
    for c in cortes:
        colocar(_whoosh(0.32, rng), max(0, c - 0.16), 0.25)
    if inicio_pergunta is not None:
        colocar(_sino(), inicio_pergunta, 0.8)
    estereo = np.stack([trilha, trilha], axis=1) * 0.7
    return _salvar(destino / "efeitos.wav", estereo)
