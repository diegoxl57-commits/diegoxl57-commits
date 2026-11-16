"""Publicação pelo Zernio (publicar.via_zernio), com a API do Zernio simulada.

Rode com:  cd noticias-tiktok && python -m pytest tests -q
"""
from types import SimpleNamespace

import pytest

from noticias import main, publicar
from noticias.config import carregar


class Resposta(SimpleNamespace):
    def json(self):
        return self.corpo


def ok(corpo=None, status=200):
    return Resposta(status_code=status, corpo=corpo or {}, text=str(corpo))


@pytest.fixture
def zernio(monkeypatch, tmp_path):
    """Simula o Zernio e guarda as chamadas feitas pelo robô."""
    chamadas = {"requests": [], "put": [], "estados": ["uploading", "published"]}

    def request(metodo, url, timeout=None, headers=None, **kw):
        caminho = url.replace(publicar.URL_ZERNIO, "")
        chamadas["requests"].append((metodo, caminho, kw, headers))
        if caminho == "/media/presign":
            return ok({"uploadUrl": "https://armazenamento/up", "publicUrl": "https://cdn/v.mp4"})
        if caminho == "/accounts":
            return ok({"accounts": [{"_id": "conta-tt", "platform": "tiktok", "username": "@diego", "isActive": True}]})
        if metodo == "POST" and caminho == "/posts":
            return ok({"post": {"_id": "p1", "status": "publishing",
                                "platforms": [{"platform": "tiktok", "status": chamadas["estados"][0]}]}}, 201)
        if metodo == "GET" and caminho == "/posts/p1":
            return ok({"post": {"_id": "p1", "status": "published", "platforms": [
                {"platform": "tiktok", "status": chamadas["estados"][1], "platformPostId": "7300",
                 "platformPostUrl": "https://www.tiktok.com/@diego/video/7300", "errorMessage": "recusado"}]}})
        raise AssertionError(f"chamada inesperada: {metodo} {caminho}")

    def put(url, data=None, headers=None, timeout=None):
        chamadas["put"].append((url, headers, data.read()))
        return ok()

    monkeypatch.setattr(publicar.requests, "request", request)
    monkeypatch.setattr(publicar.requests, "put", put)
    monkeypatch.setattr(publicar.time, "sleep", lambda s: None)
    video = tmp_path / "video.mp4"
    video.write_bytes(b"MP4FAKE")
    return chamadas, video


def cfg_zernio(**zernio):
    cfg = carregar()
    cfg["publicacao"] = dict(cfg["publicacao"], metodo="zernio", zernio={"conta": "", **zernio})
    return cfg


def test_publica_publico_com_selo_de_ia(zernio):
    chamadas, video = zernio
    r = publicar.via_zernio(cfg_zernio(), video, "Legenda da notícia\n\n#noticias", "chave-teste")

    assert chamadas["put"] == [("https://armazenamento/up", {"Content-Type": "video/mp4"}, b"MP4FAKE")]
    post = next(kw["json"] for m, c, kw, h in chamadas["requests"] if m == "POST" and c == "/posts")
    assert post["content"] == "Legenda da notícia\n\n#noticias"
    assert post["mediaItems"] == [{"type": "video", "url": "https://cdn/v.mp4"}]
    assert post["platforms"] == [{"platform": "tiktok", "accountId": "conta-tt"}]
    assert post["publishNow"] is True
    ajustes = post["tiktokSettings"]
    assert ajustes["privacyLevel"] == "PUBLIC_TO_EVERYONE"
    assert ajustes["videoMadeWithAi"] is True
    assert ajustes["contentPreviewConfirmed"] is True and ajustes["expressConsentGiven"] is True
    assert all(h == {"Authorization": "Bearer chave-teste"} for _, _, _, h in chamadas["requests"])
    assert r == {"metodo": "zernio", "post_id": "p1", "status": "published", "video_id": "7300",
                 "url": "https://www.tiktok.com/@diego/video/7300", "avisos": None}


def test_usa_a_conta_do_config_sem_listar(zernio):
    chamadas, video = zernio
    publicar.via_zernio(cfg_zernio(conta="conta-escolhida"), video, "x", "k")
    assert not any(c == "/accounts" for _, c, _, _ in chamadas["requests"])
    post = next(kw["json"] for m, c, kw, h in chamadas["requests"] if m == "POST" and c == "/posts")
    assert post["platforms"][0]["accountId"] == "conta-escolhida"


def test_falha_no_tiktok_vira_erro(zernio):
    chamadas, video = zernio
    chamadas["estados"] = ["uploading", "failed"]
    with pytest.raises(publicar.ErroPublicacao, match="recusado"):
        publicar.via_zernio(cfg_zernio(), video, "x", "k")


def test_erro_http_do_zernio_vira_erro(monkeypatch, tmp_path):
    monkeypatch.setattr(publicar.requests, "request",
                        lambda *a, **kw: Resposta(status_code=401, corpo={}, text="chave inválida"))
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    with pytest.raises(publicar.ErroPublicacao, match="401"):
        publicar.via_zernio(cfg_zernio(), video, "x", "k")


def test_publicar_escolhe_o_zernio(monkeypatch, tmp_path):
    monkeypatch.setenv("ZERNIO_API_KEY", "k")
    monkeypatch.setattr(publicar, "via_zernio", lambda cfg, video, legenda, chave: {"metodo": "zernio", "chave": chave})
    assert publicar.publicar(cfg_zernio(), tmp_path / "v.mp4", "x") == {"metodo": "zernio", "chave": "k"}


def test_chaves_faltando_pede_a_chave_do_zernio(monkeypatch):
    for nome in ("ANTHROPIC_API_KEY", "GOOGLE_TTS_API_KEY"):
        monkeypatch.setenv(nome, "x")
    monkeypatch.setenv("PUBLICAR", "true")
    monkeypatch.delenv("ZERNIO_API_KEY", raising=False)
    assert main.chaves_faltando(cfg_zernio()) == ["ZERNIO_API_KEY"]
    monkeypatch.setenv("ZERNIO_API_KEY", "k")
    assert main.chaves_faltando(cfg_zernio()) == []
