"""Busca os números de cada vídeo publicado e guarda no histórico."""
import re
from datetime import datetime, timedelta, timezone

from . import tiktok_api


def _normal(texto: str) -> str:
    return re.sub(r"[^a-z0-9à-ÿ]", "", (texto or "").lower())


def atualizar(historico: list[dict], cfg: dict) -> str:
    m = cfg.get("metricas", {})
    if not m.get("ativo", True):
        return "Leitura de métricas desligada no config.yaml."
    if not tiktok_api.configurado():
        return "Sem os secrets TIKTOK_*: o robô continua variando o formato, mas ainda não lê os números do TikTok."

    agora = datetime.now(timezone.utc)
    limite = agora - timedelta(days=int(m.get("dias_acompanhamento", 7)))
    alvos = [h for h in historico if h.get("publicado") and datetime.fromisoformat(h["quando"]) >= limite]
    if not alvos:
        return "Nenhum vídeo publicado recentemente para medir."

    try:
        videos = tiktok_api.listar_videos(maximo=80)
    except tiktok_api.ErroTikTok as e:
        return f"Não consegui ler as métricas: {e}"

    atualizados = 0
    for h in alvos:
        v = _encontrar(h, videos)
        if not v:
            continue
        criado = datetime.fromtimestamp(int(v.get("create_time", 0)), timezone.utc)
        h["video_id"] = str(v["id"])
        h["link_tiktok"] = v.get("share_url")
        h["metricas"] = {
            "visualizacoes": int(v.get("view_count") or 0),
            "curtidas": int(v.get("like_count") or 0),
            "comentarios": int(v.get("comment_count") or 0),
            "compartilhamentos": int(v.get("share_count") or 0),
            "horas_no_ar": round((agora - criado).total_seconds() / 3600, 1),
            "coletado_em": agora.isoformat(timespec="seconds"),
        }
        atualizados += 1
    return f"Métricas atualizadas de {atualizados} de {len(alvos)} vídeos recentes."


def _encontrar(h: dict, videos: list[dict]) -> dict | None:
    if h.get("video_id"):
        return next((v for v in videos if str(v.get("id")) == h["video_id"]), None)
    inicio = _normal(h.get("legenda_inicio", ""))[:40]
    if not inicio:
        return None
    publicado = datetime.fromisoformat(h["quando"])
    candidatos = []
    for v in videos:
        texto = _normal(v.get("video_description") or v.get("title") or "")
        criado = datetime.fromtimestamp(int(v.get("create_time", 0)), timezone.utc)
        diferenca = (criado - publicado).total_seconds()
        if texto.startswith(inicio) and -1800 <= diferenca <= 6 * 3600:
            candidatos.append((abs(diferenca), v))
    return min(candidatos, key=lambda c: c[0])[1] if candidatos else None
