"""Publicação no TikTok: pelo Upload-Post ou pela API oficial do TikTok."""
import time
from pathlib import Path

import requests

from . import tiktok_api
from .config import segredo

URL_UPLOADPOST = "https://api.upload-post.com/api/upload"
URL_ZERNIO = "https://zernio.com/api/v1"


class ErroPublicacao(RuntimeError):
    pass


def publicar(cfg: dict, video: Path, legenda: str) -> dict:
    metodo = cfg["publicacao"].get("metodo", "uploadpost")
    if metodo == "zernio":
        return via_zernio(cfg, video, legenda, segredo("ZERNIO_API_KEY"))
    if metodo == "uploadpost":
        return via_uploadpost(cfg, video, legenda, segredo("UPLOADPOST_API_KEY"))
    if metodo == "tiktok":
        return via_tiktok(cfg, video, legenda)
    if metodo == "tiktok_rascunho":
        return via_tiktok_rascunho(video)
    raise ErroPublicacao(f"Método de publicação desconhecido: {metodo}")


# ---------------------------------------------------------------- Zernio
# Publicação direta e pública pelo app do Zernio, já aprovado pelo TikTok (grátis até 2 contas).
def _zernio(metodo: str, caminho: str, api_key: str, timeout: int = 120, **kw) -> dict:
    resp = requests.request(metodo, URL_ZERNIO + caminho, timeout=timeout,
                            headers={"Authorization": f"Bearer {api_key}"}, **kw)
    if resp.status_code >= 400:
        raise ErroPublicacao(f"Zernio respondeu {resp.status_code} em {caminho}: {resp.text[:500]}")
    try:
        return resp.json()
    except ValueError:
        return {}


def _conta_tiktok_zernio(api_key: str, conta: str) -> str:
    """Id da conta do TikTok no Zernio: a do config.yaml ou a única conectada."""
    if conta:
        return conta
    contas = [c for c in _zernio("GET", "/accounts", api_key, params={"platform": "tiktok"}).get("accounts", [])
              if c.get("platform") == "tiktok" and c.get("isActive", True)]
    if not contas:
        raise ErroPublicacao("Nenhuma conta do TikTok conectada no Zernio.")
    if len(contas) > 1:
        print(f"[zernio] {len(contas)} contas do TikTok conectadas; usando {contas[0].get('username')}. "
              "Para escolher outra, preencha publicacao.zernio.conta no config.yaml.")
    return contas[0]["_id"]


def _id_video(valor) -> str | None:
    texto = str(valor or "").strip()
    return texto if texto.isdigit() else None


def _alvo_tiktok(post: dict) -> dict:
    return next((p for p in post.get("platforms", []) if p.get("platform") == "tiktok"), {})


def via_zernio(cfg: dict, video: Path, legenda: str, api_key: str) -> dict:
    pub = cfg["publicacao"]
    zc = pub.get("zernio") or {}

    # 1. envia o arquivo para o armazenamento do Zernio
    pre = _zernio("POST", "/media/presign", api_key,
                  json={"filename": video.name, "contentType": "video/mp4", "size": video.stat().st_size})
    with open(video, "rb") as f:
        envio = requests.put(pre["uploadUrl"], data=f, headers={"Content-Type": "video/mp4"}, timeout=900)
    if envio.status_code >= 400:
        raise ErroPublicacao(f"Falha ao enviar o vídeo ao Zernio: {envio.status_code} {envio.text[:300]}")

    # 2. publica na hora, público, com o selo de conteúdo gerado por IA
    corpo = {
        "content": legenda[:2200],
        "mediaItems": [{"type": "video", "url": pre["publicUrl"]}],
        "platforms": [{"platform": "tiktok", "accountId": _conta_tiktok_zernio(api_key, zc.get("conta", ""))}],
        "publishNow": True,
        "tiktokSettings": {
            "privacyLevel": zc.get("privacidade", "PUBLIC_TO_EVERYONE"),
            "allowComment": bool(pub.get("permitir_comentarios", True)),
            "allowDuet": True,
            "allowStitch": True,
            "videoMadeWithAi": bool(pub.get("marcar_como_ia", True)),
            "videoCoverTimestampMs": 400,  # capa com o gancho na tela
            # o dono da conta ligou a publicação automática (publicacao.metodo: zernio)
            "contentPreviewConfirmed": True,
            "expressConsentGiven": True,
        },
    }
    resposta = _zernio("POST", "/posts", api_key, json=corpo, timeout=900)
    post = resposta.get("post") or {}
    alvo = _alvo_tiktok(post)

    # 3. o TikTok processa o vídeo por alguns minutos; acompanha até publicar ou falhar
    for _ in range(30):
        if alvo.get("status") in ("published", "failed") or not post.get("_id"):
            break
        time.sleep(10)
        post = _zernio("GET", f"/posts/{post['_id']}", api_key).get("post") or post
        alvo = _alvo_tiktok(post)
    if alvo.get("status") == "failed" or post.get("status") == "failed":
        raise ErroPublicacao(f"Zernio não publicou no TikTok: {alvo.get('errorMessage') or resposta}")
    return {"metodo": "zernio", "post_id": post.get("_id"), "status": alvo.get("status") or post.get("status"),
            # só aceita id numérico do TikTok; "v_pub_url~..." é o id do envio e confundiria as métricas
            "video_id": _id_video(alvo.get("platformPostId")), "url": alvo.get("platformPostUrl"),
            "avisos": resposta.get("warnings")}


# ---------------------------------------------------------------- Upload-Post
def via_uploadpost(cfg: dict, video: Path, legenda: str, api_key: str) -> dict:
    pub = cfg["publicacao"]
    up = pub.get("uploadpost", {})
    campos = [("user", up.get("perfil", "noticias")), ("platform[]", "tiktok"), ("title", legenda)]
    if pub.get("marcar_como_ia", True):
        campos.append(("is_aigc", "true"))
    if not pub.get("permitir_comentarios", True):
        campos.append(("disable_comment", "true"))
    campos += [(k, str(v)) for k, v in (up.get("campos_extras") or {}).items()]

    with open(video, "rb") as f:
        resp = requests.post(
            URL_UPLOADPOST,
            headers={"Authorization": f"Apikey {api_key}"},
            data=campos,
            files={"video": (video.name, f, "video/mp4")},
            timeout=900,
        )
    if resp.status_code >= 400:
        raise ErroPublicacao(f"Upload-Post respondeu {resp.status_code}: {resp.text[:500]}")
    try:
        corpo = resp.json()
    except ValueError:
        corpo = {"resposta": resp.text[:500]}
    if isinstance(corpo, dict) and corpo.get("success") is False:
        raise ErroPublicacao(f"Upload-Post recusou o envio: {corpo}")
    return {"metodo": "uploadpost", "resposta": corpo}


# ---------------------------------------------------------------- API oficial
def via_tiktok(cfg: dict, video: Path, legenda: str) -> dict:
    for nome in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"):
        segredo(nome)
    pub = cfg["publicacao"]
    info = tiktok_api.post("/post/publish/creator_info/query/", {})
    opcoes = info.get("privacy_level_options", [])
    privacidade = "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in opcoes else "SELF_ONLY"
    if privacidade == "SELF_ONLY":
        print("[tiktok] Publicação pública indisponível (app ainda sem auditoria): o vídeo ficará privado.")

    tamanho, pedaco, total_pedacos = _pedacos(video)
    inicio = tiktok_api.post("/post/publish/video/init/", {
        "post_info": {
            "title": legenda[:2200],
            "privacy_level": privacidade,
            "disable_duet": False,
            "disable_stitch": False,
            "disable_comment": not pub.get("permitir_comentarios", True) or info.get("comment_disabled", False),
            "video_cover_timestamp_ms": 400,  # capa com o gancho na tela
            "is_aigc": bool(pub.get("marcar_como_ia", True)),
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": tamanho,
            "chunk_size": pedaco,
            "total_chunk_count": total_pedacos,
        },
    })
    publish_id = inicio["publish_id"]
    _enviar_arquivo(video, inicio["upload_url"], pedaco, total_pedacos)

    status = "processando"
    for _ in range(60):
        time.sleep(5)
        st = tiktok_api.post("/post/publish/status/fetch/", {"publish_id": publish_id})
        if st.get("status") == "FAILED":
            raise ErroPublicacao(f"TikTok recusou o vídeo: {st.get('fail_reason')}")
        if st.get("status") == "PUBLISH_COMPLETE":
            status = st
            break
    ids = (status.get("publicaly_available_post_id") or []) if isinstance(status, dict) else []
    return {"metodo": "tiktok", "publish_id": publish_id, "privacidade": privacidade,
            "video_id": str(ids[0]) if ids else None, "status": status}


def via_tiktok_rascunho(video: Path) -> dict:
    """Envia o vídeo para a caixa de entrada do TikTok (escopo video.upload).

    O TikTok avisa no app; você abre, cola a legenda, ativa o rótulo de IA e publica.
    Esse caminho não depende da auditoria do app.
    """
    for nome in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"):
        segredo(nome)
    tamanho, pedaco, total_pedacos = _pedacos(video)
    inicio = tiktok_api.post("/post/publish/inbox/video/init/", {
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": tamanho,
            "chunk_size": pedaco,
            "total_chunk_count": total_pedacos,
        },
    })
    publish_id = inicio["publish_id"]
    _enviar_arquivo(video, inicio["upload_url"], pedaco, total_pedacos)

    status = "processando"
    for _ in range(36):
        time.sleep(5)
        st = tiktok_api.post("/post/publish/status/fetch/", {"publish_id": publish_id})
        if st.get("status") == "FAILED":
            raise ErroPublicacao(f"TikTok recusou o vídeo: {st.get('fail_reason')}")
        if st.get("status") in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
            status = st["status"]
            break
    return {"metodo": "tiktok_rascunho", "publish_id": publish_id, "status": status}


def _pedacos(video: Path) -> tuple[int, int, int]:
    tamanho = video.stat().st_size
    pedaco = tamanho if tamanho <= 64 * 1024 * 1024 else 10 * 1024 * 1024
    return tamanho, pedaco, max(1, tamanho // pedaco)


def _enviar_arquivo(video: Path, upload_url: str, pedaco: int, total_pedacos: int) -> None:
    tamanho = video.stat().st_size
    with open(video, "rb") as f:
        for i in range(total_pedacos):
            ini = i * pedaco
            fim = tamanho - 1 if i == total_pedacos - 1 else ini + pedaco - 1  # último leva o resto
            f.seek(ini)
            dados = f.read(fim - ini + 1)
            r = requests.put(
                upload_url, data=dados, timeout=600,
                headers={"Content-Type": "video/mp4", "Content-Length": str(len(dados)),
                         "Content-Range": f"bytes {ini}-{fim}/{tamanho}"},
            )
            if r.status_code not in (200, 201, 206):
                raise ErroPublicacao(f"Falha no envio do pedaço {i + 1}: {r.status_code} {r.text[:300]}")
