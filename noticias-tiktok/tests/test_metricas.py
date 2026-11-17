"""Leitura das métricas (metricas.atualizar), com a API do TikTok simulada.

Rode com:  cd noticias-tiktok && python -m pytest tests -q
"""
from datetime import datetime, timedelta, timezone

from noticias import metricas
from noticias.config import carregar

AGORA = datetime.now(timezone.utc)


def video(id_, descricao, horas_atras, views=100):
    return {"id": id_, "video_description": descricao, "create_time": int((AGORA - timedelta(hours=horas_atras)).timestamp()),
            "share_url": f"https://tiktok/{id_}", "view_count": views, "like_count": 1, "comment_count": 0, "share_count": 0}


def registro(legenda, horas_atras, video_id=None):
    return {"legenda_inicio": legenda, "publicado": True, "video_id": video_id,
            "quando": (AGORA - timedelta(hours=horas_atras)).isoformat(timespec="seconds")}


def rodar(monkeypatch, historico, videos, metodo):
    monkeypatch.setattr(metricas.tiktok_api, "configurado", lambda: True)
    monkeypatch.setattr(metricas.tiktok_api, "listar_videos", lambda maximo=80: videos)
    cfg = carregar()
    cfg["publicacao"]["metodo"] = metodo
    return metricas.atualizar(historico, cfg)


def test_rascunho_publicado_horas_depois_e_reconhecido_mesmo_com_metodo_zernio(monkeypatch):
    # rascunho gerado há 30 h e publicado à mão há 20 h; o método atual é o Zernio
    h = [registro("Pela primeira vez, Carlos Alcaraz levanta o troféu", 30)]
    v = [video("111", "Pela primeira vez, Carlos Alcaraz levanta o troféu do Masters", 20)]
    assert rodar(monkeypatch, h, v, "zernio") == "Métricas atualizadas de 1 de 1 vídeos recentes."
    assert h[0]["video_id"] == "111" and h[0]["metricas"]["visualizacoes"] == 100


def test_video_id_conhecido_e_lido_direto(monkeypatch):
    h = [registro("qualquer começo", 5, video_id="222")]
    v = [video("222", "#RoboNoticias", 4, views=360)]
    rodar(monkeypatch, h, v, "zernio")
    assert h[0]["metricas"]["visualizacoes"] == 360


def test_legenda_diferente_nao_e_reconhecida(monkeypatch):
    h = [registro("Pela primeira vez, Carlos Alcaraz", 10)]
    v = [video("333", "#RoboNoticias", 5)]
    assert rodar(monkeypatch, h, v, "tiktok_rascunho") == "Métricas atualizadas de 0 de 1 vídeos recentes."
    assert h[0]["video_id"] is None
