"""Aviso no GitHub com a legenda pronta para colar no TikTok (modo rascunho).

Comenta numa issue fixa do repositório. O app do GitHub no celular notifica cada
comentário, e o texto vem num bloco fácil de copiar.
"""
import os

import requests

TITULO = "Vídeos prontos para publicar no TikTok"


def avisar(pauta: dict, legenda: str, formato: dict) -> str | None:
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("[aviso] Sem GITHUB_TOKEN: legenda não enviada ao GitHub (veja o resumo da rodada).")
        return None
    api = f"https://api.github.com/repos/{repo}"
    cab = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
           "X-GitHub-Api-Version": "2022-11-28"}

    numero = None
    r = requests.get(f"{api}/issues", headers=cab, params={"state": "open", "per_page": 50}, timeout=30)
    r.raise_for_status()
    for issue in r.json():
        if issue.get("title") == TITULO and "pull_request" not in issue:
            numero = issue["number"]
            break
    if numero is None:
        r = requests.post(f"{api}/issues", headers=cab, timeout=30, json={
            "title": TITULO,
            "body": ("Cada vídeo novo aparece aqui como comentário, com a legenda pronta.\n\n"
                     "Ative as notificações do app do GitHub para este repositório."),
        })
        r.raise_for_status()
        numero = r.json()["number"]

    fontes = "\n".join(f"- [{p['veiculo']}]({p['link']})" for p in pauta.get("posts_usados", []))
    corpo = (
        f"## {pauta['gancho_tela']}\n"
        f"**{pauta['titulo_tela']}**\n\n"
        "O vídeo já está na **caixa de entrada do seu TikTok** (notificação do app).\n\n"
        "1. Abra a notificação do TikTok e toque em editar.\n"
        "2. Copie a legenda abaixo e cole na descrição.\n"
        "3. Em **Mais opções**, ative **Conteúdo gerado por IA**.\n"
        "4. Se quiser, escolha um som em alta com volume baixo.\n"
        "5. Publique como **Todos**.\n\n"
        "**Legenda:**\n"
        f"```\n{legenda}\n```\n\n"
        f"**Fontes conferidas:**\n{fontes}\n\n"
        f"<sub>Formato: gancho {formato.get('gancho')} · {formato.get('duracao')} · "
        f"ritmo {formato.get('ritmo')} · trilha {formato.get('musica')}. "
        "Cole a legenda sem mudar o começo: é por ele que o robô reconhece o vídeo para medir os números.</sub>"
    )
    r = requests.post(f"{api}/issues/{numero}/comments", headers=cab, json={"body": corpo}, timeout=30)
    r.raise_for_status()
    return r.json().get("html_url")
