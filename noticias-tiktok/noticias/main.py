"""Executa uma rodada completa: coleta → pauta → narração → vídeo → publicação.

Uso:
    python -m noticias.main             # rodada normal (publica só se PUBLICAR=true)
    python -m noticias.main --demo      # usa dados de exemplo; não precisa de nenhuma chave
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from . import coleta_x, editor, estado, narracao, publicar, render, visual
from .config import RAIZ, SAIDA, carregar, segredo


def resumo_github(texto: str) -> None:
    caminho = os.environ.get("GITHUB_STEP_SUMMARY")
    if caminho:
        with open(caminho, "a", encoding="utf-8") as f:
            f.write(texto + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="usa posts e pauta de exemplo")
    ap.add_argument("--publicar", action="store_true", help="publica mesmo sem PUBLICAR=true")
    args = ap.parse_args()

    cfg = carregar()
    vai_publicar = (args.publicar or os.environ.get("PUBLICAR", "").lower() == "true") and not args.demo
    pasta = SAIDA / datetime.now().strftime("%Y%m%d-%H%M%S")
    pasta.mkdir(parents=True, exist_ok=True)
    historico = estado.carregar()

    # 1. coleta
    if args.demo:
        posts = json.loads((RAIZ / "exemplos" / "posts_exemplo.json").read_text(encoding="utf-8"))
    else:
        posts = coleta_x.buscar_posts(cfg, segredo("X_BEARER_TOKEN"))
    usados = estado.posts_ja_usados(historico)
    posts = [p for p in posts if p["id"] not in usados]
    print(f"[coleta] {len(posts)} posts novos.")

    # 2. pauta e roteiro
    if args.demo and not os.environ.get("ANTHROPIC_API_KEY"):
        pauta = json.loads((RAIZ / "exemplos" / "pauta_exemplo.json").read_text(encoding="utf-8"))
    else:
        try:
            recentes = estado.assuntos_recentes(historico, int(cfg["editor"].get("evitar_repetir_dias", 3)))
            pauta = editor.escolher_pauta(cfg, posts, recentes)
        except editor.SemPauta as e:
            print(f"[editor] Sem vídeo nesta rodada: {e}")
            resumo_github(f"### Sem vídeo nesta rodada\n{e}")
            return 0
    print(f"[editor] Pauta: {pauta['titulo_tela']}")
    (pasta / "pauta.json").write_text(json.dumps(pauta, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3. narração
    chave_voz = segredo("ELEVENLABS_API_KEY", obrigatorio=not args.demo)
    if chave_voz:
        audio, palavras = narracao.narrar(cfg, pauta["roteiro"], pasta, chave_voz)
    else:
        print("[narracao] Sem ELEVENLABS_API_KEY: usando áudio mudo de demonstração.")
        audio, palavras = narracao.narracao_simulada(pauta["roteiro"], pasta)

    # 4. vídeo
    fundos = visual.baixar_fundos(
        pauta.get("palavras_chave_imagens", []), int(cfg["video"].get("clipes_fundo", 4)),
        pasta, segredo("PEXELS_API_KEY", obrigatorio=False),
    )
    alternativo = None if fundos else visual.fundo_gerado(cfg, pasta)
    manchete = visual.camada_manchete(cfg, pauta, pasta)
    legendas = render.legendas_ass(cfg, palavras, pasta)
    video = render.montar(cfg, pasta, audio, legendas, manchete, [f["arquivo"] for f in fundos], alternativo)
    print(f"[video] {video} ({render.duracao(video):.1f}s)")

    # 5. publicação
    legenda = editor.texto_publicacao(pauta)
    resultado = {"publicado": False, "motivo": "modo de teste (PUBLICAR diferente de true)"}
    if vai_publicar:
        resultado = {"publicado": True, **publicar.publicar(cfg, video, legenda)}
        print(f"[publicacao] Enviado: {resultado}")
    else:
        print("[publicacao] Modo de teste: vídeo gerado, mas não publicado.")

    creditos = [{"autor": f["autor"], "url": f["url"]} for f in fundos]
    (pasta / "resumo.json").write_text(json.dumps({
        "titulo": pauta["titulo_tela"], "legenda": legenda, "fontes": pauta.get("posts_usados", []),
        "creditos_imagens": creditos, "resultado": resultado,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    if not args.demo:
        estado.registrar(historico, {
            "assunto": pauta.get("assunto_resumido") or pauta["titulo_tela"],
            "titulo": pauta["titulo_tela"],
            "ids_posts": pauta.get("ids_posts_usados", []),
            "publicado": resultado["publicado"],
        })

    fontes_md = "\n".join(f"- {p['veiculo']}: {p['link']}" for p in pauta.get("posts_usados", []))
    resumo_github(
        f"### {pauta['titulo_tela']}\n\n"
        f"**Publicado:** {'sim' if resultado['publicado'] else 'não (modo de teste)'}\n\n"
        f"**Legenda:**\n\n{legenda}\n\n**Posts de origem:**\n{fontes_md}\n\n"
        f"O vídeo está em *Artifacts*, no fim desta página."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
