import os
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
FONTES = RAIZ / "assets" / "fonts"
ESTADO = RAIZ / "estado"
SAIDA = RAIZ / "saida"


def carregar(caminho: Path | None = None) -> dict:
    with open(caminho or RAIZ / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def segredo(nome: str, obrigatorio: bool = True) -> str | None:
    valor = os.environ.get(nome, "").strip()
    if not valor and obrigatorio:
        raise RuntimeError(
            f"Falta o segredo {nome}. Cadastre-o em Settings > Secrets and variables > Actions."
        )
    return valor or None
