"""Autoriza o robô na sua conta do TikTok e gera o TIKTOK_REFRESH_TOKEN.

Pelo celular/iPad (recomendado): use o workflow "Autorizar TikTok" no GitHub Actions.
  1ª vez: rode com o campo "retorno" vazio → o resumo da rodada mostra o link.
  Abra o link, autorize e copie o endereço para onde o navegador foi levado.
  2ª vez: rode colando esse endereço em "retorno" → o token é salvo sozinho nos Secrets.

Pelo computador:
  python scripts/tiktok_autorizar.py --client-key CHAVE --redirect-uri URL
  python scripts/tiktok_autorizar.py --client-key CHAVE --client-secret SEGREDO --redirect-uri URL --retorno "ENDEREÇO"
"""
import argparse
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# video.list = ler os números; video.upload = enviar rascunho; video.publish = publicar direto
ESCOPOS = "user.info.basic,video.list,video.upload"


def link_autorizacao(client_key: str, redirect_uri: str, escopos: str) -> str:
    return (
        "https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={client_key}&scope={escopos}&response_type=code"
        f"&redirect_uri={quote(redirect_uri, safe='')}&state={secrets.token_urlsafe(8)}"
    )


def trocar_codigo(client_key: str, client_secret: str, redirect_uri: str, retorno: str) -> dict:
    codigo = parse_qs(urlparse(retorno.strip()).query).get("code", [retorno.strip()])[0]
    r = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": unquote(codigo),
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    dados = r.json()
    if "refresh_token" not in dados:
        raise SystemExit(f"O TikTok não devolveu o token: {dados.get('error_description') or dados}")
    return dados


def modo_github() -> None:
    from noticias.tiktok_api import salvar_secret_github

    repo = os.environ["GITHUB_REPOSITORY"]
    client_key = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
    redirect = os.environ.get("TIKTOK_REDIRECT_URI", "").strip() or f"https://github.com/{repo}"
    escopos = os.environ.get("TIKTOK_ESCOPOS", "").strip() or ESCOPOS
    retorno = os.environ.get("RETORNO", "").strip()
    resumo = open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8")
    if not client_key:
        raise SystemExit("Crie a variável TIKTOK_CLIENT_KEY (aba Variables) com a Client key do app do TikTok.")

    if not retorno:
        resumo.write(
            "## Passo 1 de 2: autorize no TikTok\n\n"
            f"1. Confirme que **{redirect}** está cadastrado como *Redirect URI* no app do TikTok.\n"
            f"2. Abra este link no Safari e toque em autorizar:\n\n   **[Autorizar o robô no TikTok]"
            f"({link_autorizacao(client_key, redirect, escopos)})**\n\n"
            "3. O navegador vai abrir a página do repositório com `?code=...` no endereço. "
            "Copie o endereço inteiro.\n"
            "4. Rode o workflow **Autorizar TikTok** de novo, colando o endereço no campo *retorno*. "
            "Faça isso em poucos minutos, porque o código expira rápido.\n"
        )
        return

    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
    if not client_secret:
        raise SystemExit("Falta o secret TIKTOK_CLIENT_SECRET.")
    if not os.environ.get("GH_PAT"):
        raise SystemExit("Falta o secret GH_PAT: sem ele o token não pode ser salvo com segurança.")
    dados = trocar_codigo(client_key, client_secret, redirect, retorno)
    salvar_secret_github("TIKTOK_REFRESH_TOKEN", dados["refresh_token"])  # nunca é impresso
    dias = int(dados.get("refresh_expires_in", 0)) // 86400
    resumo.write(
        "## Passo 2 de 2: pronto!\n\n"
        "O token foi salvo no secret **TIKTOK_REFRESH_TOKEN**.\n\n"
        f"- Permissões liberadas: `{dados.get('scope')}`\n"
        f"- Validade: cerca de {dias} dias (o robô renova sozinho a cada uso)\n"
    )


def main() -> None:
    if "--github" in sys.argv:
        modo_github()
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-key", required=True)
    ap.add_argument("--client-secret")
    ap.add_argument("--redirect-uri", required=True)
    ap.add_argument("--retorno", help="endereço completo para onde o TikTok redirecionou")
    ap.add_argument("--escopos", default=ESCOPOS,
                    help="padrão: user.info.basic,video.list,video.upload (acrescente video.publish para postar direto)")
    a = ap.parse_args()
    if not a.retorno:
        print("Abra este link, autorize e copie o endereço final do navegador:\n")
        print(link_autorizacao(a.client_key, a.redirect_uri, a.escopos))
        return
    if not a.client_secret:
        raise SystemExit("Informe também --client-secret.")
    dados = trocar_codigo(a.client_key, a.client_secret, a.redirect_uri, a.retorno)
    print("Escopos liberados:", dados.get("scope"))
    print("\nCadastre este valor no secret TIKTOK_REFRESH_TOKEN:\n")
    print(dados["refresh_token"])


if __name__ == "__main__":
    main()
