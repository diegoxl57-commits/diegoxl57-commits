# Robô de notícias para o TikTok

Várias vezes por dia, sem ninguém mexer, o robô:

1. **Lê o X**: busca os posts das últimas horas de grandes veículos (g1, Folha, Estadão, CNN Brasil, UOL e outros).
2. **Escolhe a pauta**: o Claude agrupa os posts por assunto e escolhe **uma** notícia confirmada por pelo menos **2 veículos diferentes**. Boatos, acusações contra pessoas comuns, tragédias com vítimas identificadas e assuntos já cobertos nos últimos dias ficam de fora.
3. **Escreve o roteiro**: texto neutro de 45 a 60 segundos, só com fatos presentes nos posts, além da manchete, da legenda, das hashtags e das fontes.
4. **Narra**: voz brasileira da ElevenLabs, com o tempo exato de cada palavra.
5. **Monta o vídeo** 1080×1920: imagens livres de direitos (Pexels), manchete, fontes, selo "Narração gerada por IA", barra de progresso e legenda palavra por palavra.
6. **Publica no TikTok** nos horários de pico, com o rótulo de conteúdo gerado por IA.

Tudo roda de graça no **GitHub Actions**: não precisa de computador ligado nem de servidor.

```
X (posts) ─► Claude (pauta + roteiro) ─► ElevenLabs (voz) ─► FFmpeg (vídeo) ─► TikTok
```

---

## Horários de publicação

| Brasília | Por quê |
|---|---|
| 07:40 | começo do dia, deslocamento |
| 12:10 | almoço |
| 18:40 | saída do trabalho |
| 21:10 | horário nobre do TikTok |

Para mudar, edite as linhas `cron` em `.github/workflows/noticias-tiktok.yml`. Elas ficam em UTC, que é **Brasília + 3 horas**. O GitHub pode atrasar cada rodada em alguns minutos. Depois de algumas semanas, confira no **TikTok Studio → Análises → Seguidores** os horários em que o seu público está ativo e ajuste.

---

## Custos aproximados (4 vídeos por dia, cerca de 120 por mês)

| Serviço | Para quê | Custo estimado |
|---|---|---|
| API do X | ler os posts | ~US$ 0,25 por rodada (50 posts × US$ 0,005) → **~US$ 30/mês** |
| Claude (Anthropic) | pauta e roteiro | ~US$ 0,05 por rodada → **~US$ 6/mês** |
| ElevenLabs | narração | ~110 mil caracteres/mês → confira se o seu plano cobre |
| Pexels | vídeos de fundo | grátis |
| Upload-Post | publicar no TikTok | plano pago (veja o site) |
| GitHub Actions | rodar tudo | grátis |

Para gastar menos com o X, reduza `max_posts` no `config.yaml` (com 30, fica ~US$ 18/mês).

---

## Configuração passo a passo

### 1. Crie as chaves

| Secret | Onde conseguir |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `X_BEARER_TOKEN` | developer.x.com → crie um app → *Keys and tokens* → **Bearer Token**. Adicione créditos (cobrança por uso). |
| `ELEVENLABS_API_KEY` | elevenlabs.io → *Developers* → API Keys. Adicione também a voz **"Dyego Noticias"** em *Minhas vozes* (ou troque o `voice_id` no `config.yaml`). |
| `PEXELS_API_KEY` | pexels.com/api (grátis). Sem ela, o fundo vira uma arte animada. |

### 2. Escolha como publicar no TikTok

**Opção A — Upload-Post (recomendada para começar).** Os vídeos saem **públicos** desde o primeiro dia, porque o app deles já é aprovado pelo TikTok.
1. Crie a conta em upload-post.com e um perfil chamado `noticias`.
2. Conecte a sua conta do TikTok a esse perfil.
3. Copie a API key para o secret `UPLOADPOST_API_KEY`.

**Opção B — API oficial do TikTok (gratuita).** Enquanto o seu app não passa pela auditoria do TikTok, **todos os vídeos ficam privados** (só você vê), e a auditoria pode ser negada para robôs de uso pessoal.
1. Em developers.tiktok.com, crie um app com *Login Kit* e *Content Posting API* (com *Direct Post* ligado) e cadastre uma *Redirect URI* https.
2. No seu computador, rode `python scripts/tiktok_autorizar.py` (as instruções estão no topo do arquivo) para obter o refresh token.
3. Cadastre os secrets `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` e `TIKTOK_REFRESH_TOKEN`.
4. Opcional: o secret `GH_PAT` (um token do GitHub com permissão *Secrets: write* neste repositório) deixa o robô salvar sozinho o token renovado do TikTok.
5. No `config.yaml`, troque `metodo: "uploadpost"` por `metodo: "tiktok"`.

### 3. Cadastre no GitHub

No repositório: **Settings → Secrets and variables → Actions**
- Aba **Secrets**: as chaves acima.
- Aba **Variables**:
  - `ROBO_ATIVO` = `true` → liga os horários automáticos.
  - `PUBLICAR` = `false` → nos primeiros dias o robô só **gera** os vídeos, sem publicar.

> O GitHub só roda horários automáticos a partir do branch principal (`main`). Por isso o código precisa estar no `main`.

### 4. Teste

1. **Actions → Notícias TikTok → Run workflow → modo `teste`**.
2. Ao terminar, abra a rodada: o resumo mostra a manchete, a legenda e os posts de origem. O vídeo fica em **Artifacts**, no fim da página.

### 5. Ligue a publicação

Gostou dos vídeos de teste? Troque a variável `PUBLICAR` para `true`. A partir daí, cada horário gera **e publica**.

Para pausar tudo, mude `ROBO_ATIVO` para `false`.

---

## Ajustes no `config.yaml`

- **canal.nome**: nome que aparece no topo do vídeo.
- **coleta.contas**: perfis do X monitorados (use apenas veículos confiáveis).
- **coleta.minimo_fontes**: quantos veículos precisam confirmar a notícia (padrão: 2).
- **narracao.voice_id**: voz da ElevenLabs.
- **video.cor_marca / cor_destaque**: cores do canal e da palavra falada.
- **video.musica_fundo**: caminho de um MP3 livre de direitos (opcional).

## Testar no computador

```bash
cd noticias-tiktok
pip install -r requirements.txt   # e instale o FFmpeg
python -m noticias.main --demo    # gera um vídeo de exemplo em saida/, sem chaves
```

---

## Cuidados importantes

- **Responsabilidade pelo conteúdo.** O robô usa só veículos estabelecidos, exige confirmação por 2 fontes e proíbe inventar dados. Mesmo assim, notícias mudam rápido. Acompanhe os vídeos, principalmente nas primeiras semanas, e apague qualquer erro na hora.
- **Rótulo de IA.** Os vídeos levam o rótulo "gerado por IA" do TikTok e o selo na tela. Não remova: o TikTok exige isso para voz sintética.
- **Alcance.** O TikTok pode dar menos alcance a conteúdo que considera repetitivo ou pouco original. Roteiro próprio, edição e fontes visíveis ajudam. Vale variar o visual e a voz com o tempo.
- **Direitos de imagem.** O robô não reaproveita fotos nem vídeos dos posts do X: usa apenas o banco livre do Pexels.
- **Histórico.** O arquivo `estado/historico.json` guarda os assuntos já cobertos, para não repetir. Ele é atualizado a cada rodada.
