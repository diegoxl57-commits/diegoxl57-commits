"""Coleta de posts recentes de veículos de notícia na API v2 do X."""
import re
from datetime import datetime, timedelta, timezone

import requests

URL_BUSCA = "https://api.x.com/2/tweets/search/recent"
LINK_TCO = re.compile(r"https://t\.co/\S+")


class ErroX(RuntimeError):
    pass


def _montar_consulta(contas: list[str]) -> str:
    autores = " OR ".join(f"from:{c.lstrip('@')}" for c in contas)
    consulta = f"({autores}) -is:retweet -is:reply"
    if len(consulta) > 512:
        raise ErroX("A lista de contas ficou longa demais para uma busca (limite de 512 caracteres).")
    return consulta


def buscar_posts(cfg: dict, bearer_token: str) -> list[dict]:
    coleta = cfg["coleta"]
    limite = int(coleta.get("max_posts", 50))
    inicio = datetime.now(timezone.utc) - timedelta(hours=float(coleta.get("janela_horas", 8)))
    params = {
        "query": _montar_consulta(coleta["contas"]),
        "start_time": inicio.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sort_order": "recency",
        "tweet.fields": "created_at,author_id,entities,note_tweet,lang",
        "expansions": "author_id",
        "user.fields": "name,username",
    }
    cabecalhos = {"Authorization": f"Bearer {bearer_token}"}

    posts: list[dict] = []
    usuarios: dict[str, dict] = {}
    proximo = None
    while len(posts) < limite:
        params["max_results"] = max(10, min(100, limite - len(posts)))
        if proximo:
            params["next_token"] = proximo
        resp = requests.get(URL_BUSCA, params=params, headers=cabecalhos, timeout=30)
        if resp.status_code == 401:
            raise ErroX("Token do X recusado (401). Confira o secret X_BEARER_TOKEN.")
        if resp.status_code == 402:
            raise ErroX("A conta de desenvolvedor do X está sem créditos (402). Recarregue no portal do X.")
        if resp.status_code == 429:
            raise ErroX("Limite de requisições do X atingido (429). A próxima execução tenta de novo.")
        if resp.status_code >= 400:
            raise ErroX(f"Erro {resp.status_code} na API do X: {resp.text[:300]}")
        corpo = resp.json()
        for u in corpo.get("includes", {}).get("users", []):
            usuarios[u["id"]] = u
        posts.extend(corpo.get("data", []))
        proximo = corpo.get("meta", {}).get("next_token")
        if not proximo:
            break

    return [_normalizar(p, usuarios) for p in posts[:limite]]


def _normalizar(post: dict, usuarios: dict) -> dict:
    autor = usuarios.get(post.get("author_id"), {})
    usuario = autor.get("username", "desconhecido")
    texto = (post.get("note_tweet") or {}).get("text") or post.get("text", "")
    links = [
        u.get("expanded_url")
        for u in (post.get("entities") or {}).get("urls", [])
        if u.get("expanded_url") and "x.com/" not in u["expanded_url"] and "twitter.com/" not in u["expanded_url"]
    ]
    return {
        "id": post["id"],
        "fonte_usuario": usuario,
        "fonte_nome": autor.get("name", usuario),
        "texto": LINK_TCO.sub("", texto).strip(),
        "criado_em": post.get("created_at"),
        "link_post": f"https://x.com/{usuario}/status/{post['id']}",
        "link_materia": links[0] if links else None,
    }
