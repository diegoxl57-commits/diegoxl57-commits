"""Histórico do que já foi produzido: evita repetir assuntos e guarda os números de cada vídeo."""
import json
from datetime import datetime, timedelta, timezone

from .config import ESTADO

ARQUIVO = ESTADO / "historico.json"
RELATORIO = ESTADO / "desempenho.md"
LIMITE = 400


def carregar() -> list[dict]:
    if ARQUIVO.exists():
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    return []


def salvar(historico: list[dict]) -> None:
    ESTADO.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps(historico[-LIMITE:], ensure_ascii=False, indent=1), encoding="utf-8")


def salvar_relatorio(texto: str) -> None:
    ESTADO.mkdir(parents=True, exist_ok=True)
    RELATORIO.write_text(texto, encoding="utf-8")


def assuntos_recentes(historico: list[dict], dias: int) -> list[str]:
    corte = datetime.now(timezone.utc) - timedelta(days=dias)
    return [
        h["assunto"] for h in historico
        if h.get("assunto") and datetime.fromisoformat(h["quando"]) >= corte
    ]


def posts_ja_usados(historico: list[dict]) -> set[str]:
    return {i for h in historico for i in h.get("ids_posts", [])}


def registrar(historico: list[dict], item: dict) -> None:
    item["quando"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    historico.append(item)
    salvar(historico)
