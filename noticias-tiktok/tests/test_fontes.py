"""Conferência das fontes da pauta (editor.validar).

Rode com:  cd noticias-tiktok && python -m pytest tests -q
"""
import copy

import pytest

from noticias import editor


def post(id_, veiculo, texto):
    return {"id": id_, "fonte_usuario": veiculo, "fonte_nome": veiculo, "texto": texto,
            "criado_em": "2026-11-08T14:00", "link_post": f"https://exemplo/{id_}", "link_materia": None}


POSTS = [
    post("cnn1", "CNN Brasil", "Alcaraz vence Shelton e conquista o Masters de Paris pela primeira vez"),
    post("uol1", "UOL", "Carlos Alcaraz vence Ben Shelton e é campeão do Masters de Paris"),
    post("met1", "Metrópoles", "Alcaraz vence Ben Shelton e é campeão do Masters 1000 de Paris pela 1ª vez"),
    post("fol_novela", "Folha de S.Paulo",
         "'Lá na Minha Terra' traz fábula para a faixa das seis em cidade nordestina fictícia — Depois de inovar "
         "esteticamente, com uma profusão de elementos africanos na pomposa A Nobreza do Amor"),
    post("fol_alcaraz", "Folha de S.Paulo",
         "Alcaraz vence Shelton e conquista título inédito no Masters 1000 de Paris — O espanhol Carlos Alcaraz, "
         "número 3 do mundo, conquistou neste domingo (8) seu primeiro título do Masters 1000 de Paris"),
    post("g1_selic", "g1", "Copom mantém a Selic em 15% ao ano pela quarta reunião seguida"),
]

ROTEIRO = " ".join(["Carlos Alcaraz venceu Ben Shelton e levou o Masters de Paris pela primeira vez."] * 4)

PAUTA = {
    "status": "pauta", "motivo": "", "categoria": "esportes",
    "assunto_resumido": "Alcaraz vence Shelton e conquista Masters 1000 de Paris",
    "titulo_tela": "Alcaraz conquista o Masters de Paris",
    "gancho_tela": "Alcaraz campeão em Paris",
    "roteiro": ROTEIRO, "pergunta_final": "Você costuma acompanhar tênis?",
    "palavras_destaque": ["Alcaraz"], "hashtags": ["noticias", "tenis"],
    "legenda": ("Pela primeira vez, Carlos Alcaraz levanta o troféu do Masters 1000 de Paris.\n"
                "Você costuma acompanhar tênis?\n"
                "Fontes: Folha de S.Paulo, CNN Brasil, UOL, Metrópoles"),
    "fontes": ["Folha de S.Paulo", "CNN Brasil", "UOL", "Metrópoles"],
    # o caso real da rodada 7: o id da Folha apontava para a matéria da novela
    "ids_posts_usados": ["fol_novela", "cnn1", "uol1", "met1"],
    "palavras_chave_imagens": ["tennis"],
}


def validar(pauta, posts=POSTS, minimo=2):
    return editor.validar(copy.deepcopy(pauta), posts, minimo, 120)


def test_troca_o_post_errado_pelo_certo_do_mesmo_veiculo():
    p = validar(PAUTA)
    assert p["ids_posts_usados"] == ["fol_alcaraz", "cnn1", "uol1", "met1"]
    assert "fol_novela" not in p["ids_posts_usados"]
    assert p["fontes"] == ["Folha de S.Paulo", "CNN Brasil", "UOL", "Metrópoles"]
    assert any("trocado" in a for a in p["avisos_fontes"])
    assert [x["link"] for x in p["posts_usados"]][0] == "https://exemplo/fol_alcaraz"


def test_remove_veiculo_sem_post_do_assunto_e_corrige_a_legenda():
    sem_folha_certa = [x for x in POSTS if x["id"] != "fol_alcaraz"]
    p = validar(PAUTA, sem_folha_certa)
    assert p["ids_posts_usados"] == ["cnn1", "uol1", "met1"]
    assert p["fontes"] == ["CNN Brasil", "UOL", "Metrópoles"]
    assert p["legenda"].endswith("Fontes: CNN Brasil, UOL, Metrópoles")
    # o começo da legenda (usado para reconhecer o vídeo) não muda
    assert p["legenda"].startswith("Pela primeira vez, Carlos Alcaraz")
    assert any("removido" in a for a in p["avisos_fontes"])


def test_descarta_pauta_quando_sobram_poucos_veiculos():
    pauta = dict(PAUTA, ids_posts_usados=["cnn1", "fol_novela", "g1_selic"])
    sem_folha_certa = [x for x in POSTS if x["id"] != "fol_alcaraz"]
    with pytest.raises(editor.SemPauta):
        validar(pauta, sem_folha_certa)


def test_pauta_certa_passa_sem_avisos():
    pauta = dict(PAUTA, ids_posts_usados=["cnn1", "uol1", "met1"],
                 legenda=PAUTA["legenda"].replace("Folha de S.Paulo, ", ""))
    p = validar(pauta)
    assert p["ids_posts_usados"] == ["cnn1", "uol1", "met1"]
    assert p["avisos_fontes"] == []


def test_um_post_por_veiculo():
    pauta = dict(PAUTA, ids_posts_usados=["cnn1", "uol1", "met1", "fol_alcaraz", "fol_novela"])
    p = validar(pauta)
    assert p["ids_posts_usados"] == ["cnn1", "uol1", "met1", "fol_alcaraz"]


def test_termos_ignoram_acentos_anos_e_palavras_vazias():
    assert editor._termos("Campeão em Paris neste domingo de 2026") == {"campeao", "paris"}


def test_feed_sem_declaracao_em_iso_8859_1_mantem_acentos():
    from noticias.coleta_rss import ler_feed
    xml = ("<rss><channel><item><title>Notícias de São Paulo: ação no Pará</title>"
           "<link>https://exemplo/1</link><pubDate>Sun, 08 Nov 2026 14:00:00 -0300</pubDate>"
           "</item></channel></rss>").encode("cp1252")
    [item] = ler_feed(xml)
    assert item["titulo"] == "Notícias de São Paulo: ação no Pará"


def test_ids_curtos_sao_traduzidos_para_os_ids_reais(monkeypatch):
    """O modelo recebe n1, n2... e o robô traduz de volta para os ids reais antes de conferir."""
    import json
    from types import SimpleNamespace

    from noticias.config import carregar

    enviado = {}
    resposta_modelo = dict(PAUTA, ids_posts_usados=["n1", "n2", "n3"])  # n1..n3 = cnn1, uol1, met1

    class Mensagens:
        def create(self, **kw):
            enviado.update(json.loads(kw["messages"][0]["content"]))
            return SimpleNamespace(stop_reason="end_turn",
                                   content=[SimpleNamespace(type="text", text=json.dumps(resposta_modelo))],
                                   usage=SimpleNamespace(input_tokens=1, output_tokens=1))

    monkeypatch.setattr(editor.anthropic, "Anthropic", lambda: SimpleNamespace(beta=SimpleNamespace(messages=Mensagens())))
    cfg = carregar()
    variante = {"duracao": next(iter(cfg["variantes"]["duracao"])), "gancho": next(iter(cfg["variantes"]["gancho"]))}
    p = editor.escolher_pauta(cfg, POSTS, [], variante, "")
    assert [x["id"] for x in enviado["posts"]] == [f"n{i}" for i in range(1, len(POSTS) + 1)]
    assert p["ids_posts_usados"] == ["cnn1", "uol1", "met1"]
