"""Aprendizado: pontua os vídeos, escolhe o formato da próxima rodada e gera o relatório.

Funciona como um teste A/B contínuo. Cada vídeo usa uma opção de cada grupo
(gancho, duração, ritmo, música). Primeiro todas as opções são testadas um mínimo
de vezes; depois o robô usa a de melhor pontuação na maioria das rodadas e, numa
parte delas, ainda testa as outras, porque o gosto do público muda.
"""
import random
from collections import defaultdict
from statistics import mean, median

GRUPOS = ("gancho", "duracao", "ritmo", "musica")


def interacao(m: dict) -> float:
    v = max(1, m.get("visualizacoes", 0))
    return (m.get("curtidas", 0) + 2 * m.get("comentarios", 0) + 3 * m.get("compartilhamentos", 0)) / v


def pontuar(historico: list[dict], cfg: dict) -> list[dict]:
    """Pontuação relativa ao próprio canal: 1,0 = vídeo típico; 2,0 = o dobro do típico."""
    ap = cfg.get("aprendizado", {})
    horas = float(ap.get("horas_para_medir", 24))
    maduros = [h for h in historico if h.get("metricas") and h["metricas"]["horas_no_ar"] >= horas]
    if not maduros:
        return []
    base = maduros[-30:]
    med_v = median(h["metricas"]["visualizacoes"] for h in base) or 1
    med_i = median(interacao(h["metricas"]) for h in base) or 1e-6
    pv, pi = float(ap.get("peso_visualizacoes", 0.6)), float(ap.get("peso_interacao", 0.4))
    for h in maduros:
        h["pontuacao"] = round(pv * h["metricas"]["visualizacoes"] / med_v + pi * interacao(h["metricas"]) / med_i, 3)
    return maduros


def escolher_variante(historico: list[dict], cfg: dict, rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    ap = cfg.get("aprendizado", {})
    medidos = [h for h in historico if "pontuacao" in h and h.get("variante")]
    escolha, motivos = {}, {}
    for grupo in GRUPOS:
        opcoes = list(cfg["variantes"][grupo].keys())
        if not ap.get("ativo", True):
            escolha[grupo], motivos[grupo] = rng.choice(opcoes), "sorteio (aprendizado desligado)"
            continue
        notas = defaultdict(list)
        for h in medidos:
            if h["variante"].get(grupo) in opcoes:
                notas[h["variante"][grupo]].append(h["pontuacao"])
        minimo = int(ap.get("minimo_por_opcao", 3))
        poucas = [o for o in opcoes if len(notas[o]) < minimo]
        if poucas:
            menor = min(len(notas[o]) for o in poucas)
            escolha[grupo] = rng.choice([o for o in poucas if len(notas[o]) == menor])
            motivos[grupo] = "testando (poucos dados)"
        elif rng.random() < float(ap.get("exploracao", 0.2)):
            escolha[grupo], motivos[grupo] = rng.choice(opcoes), "explorando"
        else:
            escolha[grupo] = max(opcoes, key=lambda o: mean(notas[o]))
            motivos[grupo] = f"melhor desempenho ({mean(notas[escolha[grupo]]):.2f})"
    escolha["_motivos"] = motivos
    return escolha


def resumo_para_editor(historico: list[dict]) -> str:
    medidos = [h for h in historico if "pontuacao" in h]
    if len(medidos) < 4:
        return ""
    ordem = sorted(medidos, key=lambda h: h["pontuacao"], reverse=True)

    def linha(h: dict) -> str:
        m = h["metricas"]
        return (f'- "{h.get("titulo")}" | categoria {h.get("categoria")} | gancho "{h.get("gancho_tela")}" '
                f'({h.get("variante", {}).get("gancho")}) | {m["visualizacoes"]} visualizações | '
                f'interação {interacao(m) * 100:.1f}% | nota {h["pontuacao"]:.2f}')

    por_cat = defaultdict(list)
    for h in medidos:
        por_cat[h.get("categoria", "outros")].append(h["pontuacao"])
    cats = sorted(((c, mean(n), len(n)) for c, n in por_cat.items() if len(n) >= 2), key=lambda x: -x[1])
    partes = [f"{len(medidos)} vídeos medidos. Nota 1,00 = vídeo típico do canal.", "Melhores:"]
    partes += [linha(h) for h in ordem[:3]]
    partes.append("Piores:")
    partes += [linha(h) for h in ordem[-3:]]
    if cats:
        partes.append("Nota média por categoria: " + "; ".join(f"{c} {n:.2f} ({q} vídeos)" for c, n, q in cats))
    return "\n".join(partes)


def relatorio(historico: list[dict], cfg: dict) -> str:
    publicados = [h for h in historico if h.get("publicado")]
    medidos = [h for h in publicados if "pontuacao" in h]
    linhas = ["# Desempenho do canal", ""]
    linhas.append(f"Vídeos publicados: **{len(publicados)}**, com números maduros (24h ou mais): **{len(medidos)}**.")
    if not medidos:
        linhas += ["", "Ainda não há números suficientes. O relatório se preenche sozinho conforme os vídeos completam 24h no ar."]
        return "\n".join(linhas) + "\n"
    total_v = sum(h["metricas"]["visualizacoes"] for h in medidos)
    linhas += ["", f"Visualizações somadas (vídeos medidos): **{total_v:,}**".replace(",", "."),
               f"Interação média: **{mean(interacao(h['metricas']) for h in medidos) * 100:.1f}%**", ""]

    def tabela(titulo: str, chave) -> None:
        grupos = defaultdict(list)
        for h in medidos:
            grupos[chave(h)].append(h)
        linhas.extend([f"## {titulo}", "", "| Opção | Vídeos | Nota média | Visualizações médias | Interação |",
                       "|---|---|---|---|---|"])
        for nome, hs in sorted(grupos.items(), key=lambda kv: -mean(x["pontuacao"] for x in kv[1])):
            linhas.append(
                f"| {nome} | {len(hs)} | {mean(x['pontuacao'] for x in hs):.2f} | "
                f"{mean(x['metricas']['visualizacoes'] for x in hs):,.0f} | "
                f"{mean(interacao(x['metricas']) for x in hs) * 100:.1f}% |".replace(",", ".")
            )
        linhas.append("")

    for grupo, nome in (("gancho", "Estilo de gancho"), ("duracao", "Duração"), ("ritmo", "Ritmo de cortes"),
                        ("musica", "Trilha")):
        tabela(nome, lambda h, g=grupo: h.get("variante", {}).get(g, "?"))
    tabela("Horário de publicação (Brasília)", lambda h: h.get("horario_local", "?"))
    tabela("Categoria da notícia", lambda h: h.get("categoria", "?"))

    linhas += ["## Melhores vídeos", ""]
    for h in sorted(medidos, key=lambda h: -h["pontuacao"])[:5]:
        link = f" — [ver]({h['link_tiktok']})" if h.get("link_tiktok") else ""
        linhas.append(f"- **{h['pontuacao']:.2f}** · {h.get('titulo')} · "
                      f"{h['metricas']['visualizacoes']} visualizações{link}")
    return "\n".join(linhas) + "\n"
