"""Publicação no TikTok: pelo Upload-Post ou pela API oficial do TikTok."""
import time
from pathlib import Path

import requests

from . import tiktok_api
from .config import segredo

URL_UPLOADPOST = "https://api.upload-post.com/api/upload"


class ErroPublicacao(RuntimeError):
    pass


def publicar(cfg: dict, video: Path, legenda: str) -> dict:
    metodo = cfg["publicacao"].get("metodo", "uploadpost")
    if metodo == "uploadpost":
        return via_uploadpost(cfg, video, legenda, segredo("UPLOADPOST_API_KEY"))
    if metodo == "tiktok":
        return via_tiktok(cfg, video, legenda)
    raise ErroPublicacao(f"Método de publicação desconhecido: {metodo}")


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

    tamanho = video.stat().st_size
    pedaco = tamanho if tamanho <= 64 * 1024 * 1024 else 10 * 1024 * 1024
    total_pedacos = max(1, tamanho // pedaco)
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
    publish_id, upload_url = inicio["publish_id"], inicio["upload_url"]

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
