"""Gera o TIKTOK_REFRESH_TOKEN (só para quem usa a API oficial do TikTok).

Passo 1 — gerar o link de autorização:
    python scripts/tiktok_autorizar.py --client-key SUA_CHAVE --redirect-uri https://seu-site/callback

Passo 2 — abra o link, autorize com a conta do TikTok e copie o endereço para onde
o navegador foi levado (mesmo que a página dê erro). Depois:
    python scripts/tiktok_autorizar.py --client-key SUA_CHAVE --client-secret SEU_SEGREDO \
        --redirect-uri https://seu-site/callback --retorno "ENDEREÇO_COPIADO"
"""
import argparse
import secrets
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests

ESCOPOS = "user.info.basic,video.publish"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-key", required=True)
    ap.add_argument("--client-secret")
    ap.add_argument("--redirect-uri", required=True)
    ap.add_argument("--retorno", help="endereço completo para onde o TikTok redirecionou")
    a = ap.parse_args()

    if not a.retorno:
        url = (
            "https://www.tiktok.com/v2/auth/authorize/"
            f"?client_key={a.client_key}&scope={ESCOPOS}&response_type=code"
            f"&redirect_uri={quote(a.redirect_uri, safe='')}&state={secrets.token_urlsafe(8)}"
        )
        print("Abra este link, autorize e copie o endereço final do navegador:\n")
        print(url)
        return

    if not a.client_secret:
        raise SystemExit("Informe também --client-secret.")
    codigo = parse_qs(urlparse(a.retorno).query).get("code", [a.retorno])[0]
    r = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        data={
            "client_key": a.client_key,
            "client_secret": a.client_secret,
            "code": unquote(codigo),
            "grant_type": "authorization_code",
            "redirect_uri": a.redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    dados = r.json()
    if "refresh_token" not in dados:
        raise SystemExit(f"O TikTok não devolveu o token: {dados}")
    print("Escopos liberados:", dados.get("scope"))
    print("\nCadastre este valor no secret TIKTOK_REFRESH_TOKEN (vale por 1 ano):\n")
    print(dados["refresh_token"])


if __name__ == "__main__":
    main()
