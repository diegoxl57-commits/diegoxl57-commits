"""Acesso à API oficial do TikTok: token (renovado uma vez por rodada) e lista de vídeos."""
import base64
import os

import requests

TT = "https://open.tiktokapis.com/v2"
CAMPOS_VIDEO = "id,title,video_description,create_time,duration,share_url,view_count,like_count,comment_count,share_count"

_acesso: str | None = None


class ErroTikTok(RuntimeError):
    pass


def configurado() -> bool:
    return all(os.environ.get(n) for n in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"))


def acesso() -> str:
    """Token de acesso válido. O TikTok pode trocar o refresh token; o novo é salvo nos Secrets."""
    global _acesso
    if _acesso:
        return _acesso
    r = requests.post(
        f"{TT}/oauth/token/",
        data={
            "client_key": os.environ["TIKTOK_CLIENT_KEY"],
            "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
            "grant_type": "refresh_token",
            "refresh_token": os.environ["TIKTOK_REFRESH_TOKEN"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    dados = r.json()
    if r.status_code >= 400 or "access_token" not in dados:
        raise ErroTikTok(f"Não consegui renovar o acesso ao TikTok: {dados}")
    novo = dados.get("refresh_token")
    if novo and novo != os.environ["TIKTOK_REFRESH_TOKEN"]:
        salvar_secret_github("TIKTOK_REFRESH_TOKEN", novo)
        os.environ["TIKTOK_REFRESH_TOKEN"] = novo
    _acesso = dados["access_token"]
    return _acesso


def post(caminho: str, corpo: dict, params: dict | None = None) -> dict:
    r = requests.post(
        f"{TT}{caminho}", params=params, json=corpo, timeout=60,
        headers={"Authorization": f"Bearer {acesso()}", "Content-Type": "application/json; charset=UTF-8"},
    )
    dados = r.json()
    erro = dados.get("error", {})
    if r.status_code >= 400 or erro.get("code") not in (None, "ok"):
        raise ErroTikTok(f"TikTok {caminho}: {erro.get('code')} - {erro.get('message')}")
    return dados.get("data", {})


def listar_videos(maximo: int = 60) -> list[dict]:
    """Vídeos mais recentes da conta com visualizações, curtidas, comentários e compartilhamentos."""
    videos, cursor = [], None
    while len(videos) < maximo:
        corpo = {"max_count": 20}
        if cursor:
            corpo["cursor"] = cursor
        dados = post("/video/list/", corpo, params={"fields": CAMPOS_VIDEO})
        videos += dados.get("videos", [])
        if not dados.get("has_more"):
            break
        cursor = dados.get("cursor")
    return videos[:maximo]


def salvar_secret_github(nome: str, valor: str) -> None:
    """Grava um valor nos Secrets do repositório (precisa do secret GH_PAT)."""
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
