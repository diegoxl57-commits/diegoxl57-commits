"""Publicação no TikTok: pelo Upload-Post ou pela API oficial do TikTok."""
import base64
import os
import time
from pathlib import Path

import requests

from .config import segredo

URL_UPLOADPOST = "https://api.upload-post.com/api/upload"
TT = "https://open.tiktokapis.com/v2"


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
    pub = cfg["publicacao"]
    tokens = renovar_token(
        segredo("TIKTOK_CLIENT_KEY"), segredo("TIKTOK_CLIENT_SECRET"), segredo("TIKTOK_REFRESH_TOKEN")
    )
    acesso = tokens["access_token"]
    novo_refresh = tokens.get("refresh_token")
    if novo_refresh and novo_refresh != os.environ.get("TIKTOK_REFRESH_TOKEN"):
        salvar_secret_github("TIKTOK_REFRESH_TOKEN", novo_refresh)

    cab = {"Authorization": f"Bearer {acesso}", "Content-Type": "application/json; charset=UTF-8"}
    info = _tt_post(f"{TT}/post/publish/creator_info/query/", cab, {})
    opcoes = info.get("privacy_level_options", [])
    privacidade = "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in opcoes else "SELF_ONLY"
    if privacidade == "SELF_ONLY":
        print("[tiktok] Publicação pública indisponível (app ainda sem auditoria): o vídeo ficará privado.")

    tamanho = video.stat().st_size
    pedaco = tamanho if tamanho <= 64 * 1024 * 1024 else 10 * 1024 * 1024
    total_pedacos = max(1, tamanho // pedaco)
    corpo = {
        "post_info": {
            "title": legenda[:2200],
            "privacy_level": privacidade,
            "disable_duet": False,
            "disable_stitch": False,
            "disable_comment": not pub.get("permitir_comentarios", True) or info.get("comment_disabled", False),
            "video_cover_timestamp_ms": 800,
            "is_aigc": bool(pub.get("marcar_como_ia", True)),
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": tamanho,
            "chunk_size": pedaco,
            "total_chunk_count": total_pedacos,
        },
    }
    inicio = _tt_post(f"{TT}/post/publish/video/init/", cab, corpo)
    publish_id, upload_url = inicio["publish_id"], inicio["upload_url"]

    with open(video, "rb") as f:
        for i in range(total_pedacos):
            ini = i * pedaco
            fim = tamanho - 1 if i == total_pedacos - 1 else ini + pedaco - 1  # último leva o resto
            f.seek(ini)
            dados = f.read(fim - ini + 1)
            r = requests.put(
                upload_url,
                data=dados,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(dados)),
                    "Content-Range": f"bytes {ini}-{fim}/{tamanho}",
                },
                timeout=600,
            )
            if r.status_code not in (200, 201, 206):
                raise ErroPublicacao(f"Falha no envio do pedaço {i + 1}: {r.status_code} {r.text[:300]}")

    for _ in range(60):
        time.sleep(5)
        st = _tt_post(f"{TT}/post/publish/status/fetch/", cab, {"publish_id": publish_id})
        if st.get("status") == "PUBLISH_COMPLETE":
            return {"metodo": "tiktok", "publish_id": publish_id, "privacidade": privacidade, "status": st}
        if st.get("status") == "FAILED":
            raise ErroPublicacao(f"TikTok recusou o vídeo: {st.get('fail_reason')}")
    return {"metodo": "tiktok", "publish_id": publish_id, "privacidade": privacidade, "status": "processando"}


def renovar_token(client_key: str, client_secret: str, refresh_token: str) -> dict:
    r = requests.post(
        f"{TT}/oauth/token/",
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    dados = r.json()
    if r.status_code >= 400 or "access_token" not in dados:
        raise ErroPublicacao(f"Não consegui renovar o acesso ao TikTok: {dados}")
    return dados


def _tt_post(url: str, cab: dict, corpo: dict) -> dict:
    r = requests.post(url, headers=cab, json=corpo, timeout=60)
    dados = r.json()
    erro = dados.get("error", {})
    if r.status_code >= 400 or erro.get("code") not in (None, "ok"):
        raise ErroPublicacao(f"TikTok {url.rsplit('/v2/', 1)[-1]}: {erro.get('code')} - {erro.get('message')}")
    return dados.get("data", {})


def salvar_secret_github(nome: str, valor: str) -> None:
    """Grava o novo refresh token do TikTok nos Secrets do repositório (precisa do secret GH_PAT)."""
    pat, repo = os.environ.get("GH_PAT"), os.environ.get("GITHUB_REPOSITORY")
    if not pat or not repo:
        print(f"[aviso] O TikTok gerou um novo {nome}, mas GH_PAT não está configurado para salvá-lo.")
        return
    from nacl import encoding, public

    cab = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json",
           "X-GitHub-Api-Version": "2022-11-28"}
    chave = requests.get(f"https://api.github.com/repos/{repo}/actions/secrets/public-key", headers=cab, timeout=30)
    chave.raise_for_status()
    k = chave.json()
    caixa = public.SealedBox(public.PublicKey(k["key"].encode(), encoding.Base64Encoder()))
    cifrado = base64.b64encode(caixa.encrypt(valor.encode())).decode()
    r = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{nome}",
        headers=cab, json={"encrypted_value": cifrado, "key_id": k["key_id"]}, timeout=30,
    )
    r.raise_for_status()
    print(f"[ok] {nome} atualizado nos Secrets do repositório.")
