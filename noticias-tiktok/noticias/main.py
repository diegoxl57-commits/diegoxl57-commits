"""Executa uma rodada completa:
métricas → formato da rodada → coleta → pauta → narração → vídeo → publicação → relatório.

Uso:
    python -m noticias.main             # rodada normal (publica só se PUBLICAR=true)
    python -m noticias.main --demo      # usa dados de exemplo; não precisa de nenhuma chave
"""
import argparse
import json
import os
import random
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from . import audio, avisos, coleta_rss, coleta_x, editor, estado, estrategia, metricas, narracao, publicar, render, visual
from .config import RAIZ, SAIDA, carregar, segredo


def horario_da_rodada(fuso: ZoneInfo) -> str:
    """Horário agendado (Brasília) quando a rodada vem do agendador do GitHub; senão, a hora atual."""
    cron = os.environ.get("HORARIO_AGENDADO", "").split()
    if len(cron) >= 2 and cron[0].isdigit() and cron[1].isdigit():
        utc = datetime.now(ZoneInfo("UTC")).replace(hour=int(cron[1]), minute=int(cron[0]))
        return utc.astimezone(fuso).strftime("%H:%M")
    return datetime.now(fuso).strftime("%H:%M")


def chaves_faltando(cfg: dict) -> list[str]:
    """Secrets obrigatórios para a configuração atual que ainda não foram cadastrados."""
    precisa = ["ANTHROPIC_API_KEY"]
    precisa.append({"google": "GOOGLE_TTS_API_KEY", "elevenlabs": "ELEVENLABS_API_KEY"}
                   .get(cfg["narracao"].get("provedor", "google"), "GOOGLE_TTS_API_KEY"))
    if cfg["coleta"].get("fonte", "rss") == "x":
        precisa.append("X_BEARER_TOKEN")
    if os.environ.get("PUBLICAR", "").lower() == "true":
        metodo = cfg["publicacao"].get("metodo", "tiktok_rascunho")
        precisa += (["UPLOADPOST_API_KEY"] if metodo == "uploadpost"
                    else ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"])
    return [n for n in precisa if not os.environ.get(n, "").strip()]


def resumo_github(texto: str) -> None:
    caminho = os.environ.get("GITHUB_STEP_SUMMARY")
    if caminho:
        with open(caminho, "a", encoding="utf-8") as f:
            f.write(texto + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="usa posts e pauta de exemplo")
    ap.add_argument("--publicar", action="store_true", help="publica mesmo sem PUBLICAR=true")
    ap.add_argument("--formato", default=os.environ.get("FORMATO", ""),
                    help='força opções, ex.: "gancho=numero,musica=pulsante"')
    args = ap.parse_args()

    cfg = carregar()
    fuso = ZoneInfo(cfg["canal"].get("fuso_horario", "America/Sao_Paulo"))
    vai_publicar = (args.publicar or os.environ.get("PUBLICAR", "").lower() == "true") and not args.demo
    pasta = SAIDA / datetime.now().strftime("%Y%m%d-%H%M%S")
    pasta.mkdir(parents=True, exist_ok=True)
    historico = [] if args.demo else estado.carregar()
    semente = random.randrange(1_000_000)

    # 1. números dos vídeos anteriores e formato desta rodada
    if not args.demo:
        aviso = metricas.atualizar(historico, cfg)
        print(f"[metricas] {aviso}")
        estrategia.pontuar(historico, cfg)
        estado.salvar(historico)
        estado.salvar_relatorio(estrategia.relatorio(historico, cfg))
    variante = estrategia.escolher_variante(historico, cfg, random.Random(semente))
    motivos = variante.pop("_motivos")
    for par in filter(None, (x.strip() for x in args.formato.split(","))):
        grupo, _, opcao = par.partition("=")
        if grupo in cfg["variantes"] and opcao in cfg["variantes"][grupo]:
            variante[grupo], motivos[grupo] = opcao, "forçado manualmente"
    print("[formato] " + ", ".join(f"{g}={variante[g]} ({motivos[g]})" for g in estrategia.GRUPOS))

    # 2. coleta
    if args.demo:
        posts = json.loads((RAIZ / "exemplos" / "posts_exemplo.json").read_text(encoding="utf-8"))
    elif cfg["coleta"].get("fonte", "rss") == "x":
        posts = coleta_x.buscar_posts(cfg, segredo("X_BEARER_TOKEN"))
    else:
        try:
            posts = coleta_rss.buscar_noticias(cfg)
        except coleta_rss.ErroRSS as e:
            resumo_github("### Feeds de notícias\n\n| Veículo | Situação |\n|---|---|\n" + "\n".join(
                f"| {v} | {st} |" for v, st in coleta_rss.SITUACAO.items()) + f"\n\n**{e}**\n")
            print(f"[coleta] {e}")
            return 1
    usados = estado.posts_ja_usados(historico)
    posts = [p for p in posts if p["id"] not in usados]
    veiculos = len({p["fonte_usuario"] for p in posts})
    print(f"[coleta] {len(posts)} notícias novas de {veiculos} veículos.")
    if coleta_rss.SITUACAO:
        resumo_github("### Feeds de notícias\n\n| Veículo | Situação |\n|---|---|\n" + "\n".join(
            f"| {v} | {st} |" for v, st in coleta_rss.SITUACAO.items()) + "\n")

    if not args.demo:
        faltando = chaves_faltando(cfg)
        if faltando:
            msg = "Faltam estes secrets para gerar o vídeo: " + ", ".join(f"`{n}`" for n in faltando)
            print(f"[config] {msg}")
            resumo_github(f"### Configuração incompleta\n\n{msg}.\n\n"
                          "Cadastre em *Settings → Secrets and variables → Actions* e rode de novo. "
                          "O passo a passo está em `noticias-tiktok/README.md`.")
            return 1

    # 3. pauta e roteiro
    if args.demo and not os.environ.get("ANTHROPIC_API_KEY"):
        pauta = json.loads((RAIZ / "exemplos" / "pauta_exemplo.json").read_text(encoding="utf-8"))
    else:
        try:
            recentes = estado.assuntos_recentes(historico, int(cfg["editor"].get("evitar_repetir_dias", 3)))
            pauta = editor.escolher_pauta(cfg, posts, recentes, variante, estrategia.resumo_para_editor(historico))
        except editor.SemPauta as e:
            print(f"[editor] Sem vídeo nesta rodada: {e}")
            resumo_github(f"### Sem vídeo nesta rodada\n{e}")
            return 0
    print(f"[editor] Gancho: {pauta['gancho_tela']} | Título: {pauta['titulo_tela']}")
    (pasta / "pauta.json").write_text(json.dumps(pauta, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4. narração
    if not args.demo or narracao.chave_configurada(cfg):
        voz, palavras = narracao.narrar(cfg, pauta["roteiro"], pasta)
    else:
        print("[narracao] Demonstração sem chave de voz: usando áudio mudo.")
        voz, palavras = narracao.narracao_simulada(pauta["roteiro"], pasta, palavras_por_segundo=2.9)

    # 5. vídeo
    total = render.duracao(voz) + 0.6
    fim_gancho, inicio_pergunta = render.marcos(palavras, pauta.get("pergunta_final", ""))
    pontos = render.cortes(total, float(cfg["variantes"]["ritmo"][variante["ritmo"]]), semente)
    fundos = visual.baixar_fundos(
        pauta.get("palavras_chave_imagens", []), int(cfg["video"].get("clipes_fundo", 6)),
        pasta, segredo("PEXELS_API_KEY", obrigatorio=False),
    )
    imagem = None if fundos else visual.fundo_gerado(cfg, pasta)
    fundo = render.montar_fundo(cfg, pasta, pontos, total, [f["arquivo"] for f in fundos], imagem)
    trilha = audio.gerar_trilha(variante["musica"], total, pasta, semente)
    efeitos = audio.gerar_efeitos(total, pontos[1:], inicio_pergunta, pasta, semente)
    legendas = render.legendas_ass(cfg, pauta, palavras, fim_gancho, inicio_pergunta, total, pasta)
    video = render.montar(cfg, pasta, fundo, pontos, total, fim_gancho, voz, trilha, efeitos,
                          visual.vinheta(cfg, pasta), visual.faixa_topo(cfg, pauta, pasta), legendas)
    print(f"[video] {video} ({render.duracao(video):.1f}s, {len(pontos)} cenas)")

    # 6. publicação
    legenda = editor.texto_publicacao(pauta)
    resultado = {"publicado": False, "motivo": "modo de teste (PUBLICAR diferente de true)"}
    if vai_publicar:
        resultado = {"publicado": True, **publicar.publicar(cfg, video, legenda)}
        print(f"[publicacao] Enviado: {resultado}")
        if cfg["publicacao"].get("metodo") == "tiktok_rascunho" and cfg["publicacao"].get("avisar_no_github", True):
            try:
                link = avisos.avisar(pauta, legenda, variante)
                if link:
                    resultado["aviso"] = link
                    print(f"[aviso] Legenda pronta no GitHub: {link}")
            except Exception as e:  # o aviso não pode derrubar a rodada: o vídeo já está no TikTok
                print(f"[aviso] Não consegui comentar a legenda no GitHub: {e}")
    else:
        print("[publicacao] Modo de teste: vídeo gerado, mas não publicado.")

    creditos = [{"autor": f["autor"], "url": f["url"]} for f in fundos]
    (pasta / "resumo.json").write_text(json.dumps({
        "titulo": pauta["titulo_tela"], "gancho": pauta["gancho_tela"], "legenda": legenda,
        "formato": variante, "fontes": pauta.get("posts_usados", []), "creditos_imagens": creditos,
        "resultado": resultado,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # 7. histórico e relatório
    if not args.demo:
        estado.registrar(historico, {
            "assunto": pauta.get("assunto_resumido") or pauta["titulo_tela"],
            "titulo": pauta["titulo_tela"],
            "gancho_tela": pauta["gancho_tela"],
            "categoria": pauta.get("categoria"),
            "ids_posts": pauta.get("ids_posts_usados", []),
            "variante": variante,
            "duracao_s": round(total, 1),
            "horario_local": horario_da_rodada(fuso),
            "legenda_inicio": legenda[:80],
            "video_id": resultado.get("video_id"),
            "publicado": resultado["publicado"],
        })
        estado.salvar_relatorio(estrategia.relatorio(historico, cfg))

    fontes_md = "\n".join(f"- {p['veiculo']}: {p['link']}" for p in pauta.get("posts_usados", []))
    if pauta.get("avisos_fontes"):
        fontes_md += "\n\n**Fontes corrigidas pelo robô:**\n" + "\n".join(f"- {a}" for a in pauta["avisos_fontes"])
    formato_md = "\n".join(f"- {g}: **{variante[g]}** ({motivos[g]})" for g in estrategia.GRUPOS)
    resumo_github(
        f"### {pauta['gancho_tela']} — {pauta['titulo_tela']}\n\n"
        f"**Publicado:** {'sim' if resultado['publicado'] else 'não (modo de teste)'}\n\n"
        f"**Formato desta rodada:**\n{formato_md}\n\n"
        f"**Legenda:**\n\n{legenda}\n\n**Posts de origem:**\n{fontes_md}\n\n"
        f"O vídeo está em *Artifacts*, no fim desta página. "
        f"O desempenho acumulado fica em `noticias-tiktok/estado/desempenho.md`."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
