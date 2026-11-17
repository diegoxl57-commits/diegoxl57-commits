"""Checagem dos fatos (editor.revisar_fatos), com o Claude simulado.

Rode com:  cd noticias-tiktok && python -m pytest tests -q
"""
import json
from types import SimpleNamespace

import pytest

from noticias import editor
from noticias.config import carregar
from test_fontes import PAUTA, POSTS

# o editor cita CNN, UOL e Metrópoles (n1..n3), mas tirou "número 3 do mundo" do post da Folha,
# que não está entre as fontes: o mesmo tipo de erro do caso do Cantareira
ROTEIRO_EDITOR = ("Alcaraz, número 3 do mundo, venceu Ben Shelton e levou o Masters de Paris. " * 4
                  + "Você costuma acompanhar tênis?")
EDITOR = dict(PAUTA, ids_posts_usados=["n1", "n2", "n3"], roteiro=ROTEIRO_EDITOR,
              legenda="O número 3 do mundo levou Paris.\nVocê costuma acompanhar tênis?\nFontes: CNN Brasil, UOL, Metrópoles")
ROTEIRO_REVISADO = ("Carlos Alcaraz venceu Ben Shelton e levou o Masters de Paris pela primeira vez. " * 4
                    + "Você costuma acompanhar tênis?")
REVISAO = {
    "gancho_tela": PAUTA["gancho_tela"], "titulo_tela": PAUTA["titulo_tela"], "roteiro": ROTEIRO_REVISADO,
    "pergunta_final": PAUTA["pergunta_final"],
    "legenda": "Alcaraz levou Paris pela primeira vez.\nVocê costuma acompanhar tênis?\nFontes: Folha de S.Paulo",
    "cortes": ['"número 3 do mundo" saiu: não aparece nos posts das fontes.'],
}


def cliente_falso(monkeypatch, *respostas):
    """Simula o Claude: devolve as respostas na ordem e guarda o que o robô enviou."""
    chamadas, fila = [], list(respostas)

    class Mensagens:
        def create(self, **kw):
            chamadas.append({"sistema": kw["system"], "entrada": json.loads(kw["messages"][0]["content"])})
            corpo, motivo = fila.pop(0)
            return SimpleNamespace(stop_reason=motivo, content=[SimpleNamespace(type="text", text=json.dumps(corpo))],
                                   usage=SimpleNamespace(input_tokens=10, output_tokens=5))

    monkeypatch.setattr(editor.anthropic, "Anthropic", lambda: SimpleNamespace(beta=SimpleNamespace(messages=Mensagens())))
    return chamadas


def escolher():
    cfg = carregar()
    variante = {"duracao": next(iter(cfg["variantes"]["duracao"])), "gancho": next(iter(cfg["variantes"]["gancho"]))}
    return editor.escolher_pauta(cfg, POSTS, [], variante, "")


def test_checagem_le_so_os_posts_das_fontes_e_corrige_o_texto(monkeypatch):
    chamadas = cliente_falso(monkeypatch, (EDITOR, "end_turn"), (REVISAO, "end_turn"))
    p = escolher()

    checagem = chamadas[1]
    assert checagem["sistema"] == editor.SISTEMA_REVISAO
    assert [x["veiculo"] for x in checagem["entrada"]["posts"]] == ["CNN Brasil", "UOL", "Metrópoles"]
    assert not any("número 3" in x["texto"] for x in checagem["entrada"]["posts"])  # o post da Folha não vai
    assert "número 3 do mundo" in checagem["entrada"]["video"]["roteiro"]

    assert p["roteiro"] == ROTEIRO_REVISADO.strip()
    assert p["legenda"].startswith("Alcaraz levou Paris pela primeira vez.")
    assert p["legenda"].endswith("Fontes: CNN Brasil, UOL, Metrópoles")  # a linha de fontes segue a lista conferida
    assert p["cortes_fatos"] == REVISAO["cortes"]
    assert p["_uso_tokens"] == {"entrada": 20, "saida": 10}


def test_checagem_sem_cortes_mantem_o_video(monkeypatch):
    certo = dict(EDITOR, roteiro=ROTEIRO_REVISADO)
    sem_mudanca = {**{c: certo[c] for c in editor.CAMPOS_REVISADOS}, "cortes": []}
    cliente_falso(monkeypatch, (certo, "end_turn"), (sem_mudanca, "end_turn"))
    p = escolher()
    assert p["roteiro"] == ROTEIRO_REVISADO.strip()
    assert p["gancho_tela"] == PAUTA["gancho_tela"]
    assert p["cortes_fatos"] == []


def test_roteiro_curto_demais_depois_dos_cortes_descarta_a_pauta(monkeypatch):
    curto = dict(REVISAO, roteiro="Alcaraz venceu em Paris. Você costuma acompanhar tênis?")
    cliente_falso(monkeypatch, (EDITOR, "end_turn"), (curto, "end_turn"))
    with pytest.raises(editor.SemPauta, match="Depois da checagem dos fatos"):
        escolher()


def test_checagem_recusada_nao_gera_video(monkeypatch):
    cliente_falso(monkeypatch, (EDITOR, "end_turn"), ({}, "refusal"))
    with pytest.raises(editor.SemPauta, match="checagem dos fatos"):
        escolher()
