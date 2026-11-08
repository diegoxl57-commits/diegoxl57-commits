# Robô de notícias para o TikTok

Várias vezes por dia, sem ninguém mexer, o robô:

1. **Mede o que já foi ao ar**: lê no TikTok as visualizações, curtidas, comentários e compartilhamentos dos vídeos anteriores.
2. **Escolhe o formato da rodada**: estilo de gancho, duração, ritmo de cortes e trilha, priorizando o que deu mais resultado (veja "Aprendizado automático").
3. **Lê o X**: busca os posts das últimas horas de grandes veículos (g1, Folha, Estadão, CNN Brasil, UOL e outros).
4. **Escolhe a pauta e escreve**: o Claude escolhe **uma** notícia confirmada por pelo menos **2 veículos** e escreve gancho, roteiro, pergunta para comentários, legenda e hashtags. Ele recebe os números do canal para entender o que o público assiste.
5. **Narra**: voz brasileira da ElevenLabs, em ritmo de TikTok, com o tempo de cada palavra.
6. **Monta o vídeo viral** 1080×1920 (detalhes abaixo).
7. **Publica no TikTok** nos horários de pico, com o rótulo de conteúdo gerado por IA.
8. **Atualiza o relatório** `estado/desempenho.md`.

Tudo roda de graça no **GitHub Actions**: não precisa de computador ligado nem de servidor.

```
métricas do TikTok ─► formato da rodada ─► X ─► Claude ─► ElevenLabs ─► FFmpeg ─► TikTok
        ▲                                                                           │
        └───────────────────── visualizações e interação ◄──────────────────────────┘
```

---

## O formato viral

| Momento | O que acontece |
|---|---|
| 0 a ~2 s | **Gancho gigante** na tela (faixa vermelha inclinada, efeito de "pulo") enquanto a primeira frase é falada, com som de impacto. É o que segura o dedo antes da rolagem. |
| corpo | **Cortes de cena a cada 2 a 3,5 s** com zoom lento, flash e "whoosh". **Legendas grandes palavra por palavra**: a palavra falada em amarelo, números e palavras-chave em verde. |
| topo | Faixa compacta com o nome do canal, o título, as fontes e o aviso de IA, que entra logo depois do gancho. |
| final | **Pergunta para comentários** falada e na tela, com o selo "COMENTE AQUI" e um sino. Comentários pesam muito no algoritmo. |
| áudio | Voz mais enérgica, trilha original que abaixa sozinha quando a voz fala, efeitos sonoros e volume no padrão das redes (-14 LUFS). |
| duração | De 25 a 45 segundos, conforme o que performar melhor. |

A trilha e os efeitos sonoros são **gerados por código**: são originais e não têm problema de direitos autorais. Para usar músicas próprias livres de direitos, coloque arquivos MP3 em `assets/musicas/`.

**Limites que o robô sempre respeita:** o gancho precisa ser verdadeiro e entregue pelo vídeo. Exagero, "você não vai acreditar" e promessas falsas são proibidos. As regras de checagem continuam valendo: duas fontes, nada de boato, nada de dados inventados. Engajamento nunca passa por cima disso.

---

## Aprendizado automático

Cada vídeo usa uma opção de cada grupo, e o robô funciona como um **teste A/B contínuo**:

| Grupo | Opções |
|---|---|
| Gancho | pergunta · número · impacto no dia a dia · novidade · contraste |
| Duração | curto (~25-32 s) · médio (~35-45 s) |
| Ritmo | rápido (corte a cada ~2,2 s) · normal (~3,4 s) |
| Trilha | pulsante · tensa · sem música |

1. **Fase de testes**: cada opção é usada pelo menos 3 vezes.
2. **Nota de cada vídeo** (depois de 24 h no ar): 60% visualizações + 40% interação. A interação conta curtidas, comentários (peso 2) e compartilhamentos (peso 3) por visualização. A nota é relativa ao próprio canal: 1,0 é um vídeo típico e 2,0 é o dobro do típico.
3. **Daí em diante**: em 80% das rodadas o robô usa a opção de melhor nota em cada grupo. Nas outras 20%, testa uma alternativa, porque o gosto do público muda.
4. **O editor também aprende**: o Claude recebe os melhores e os piores vídeos, com gancho, categoria e números, e usa isso para escolher pautas e aberturas, sem desrespeitar as regras editoriais.

O relatório `estado/desempenho.md` mostra a nota média por gancho, duração, ritmo, trilha, **horário** e **categoria de notícia**, além dos melhores vídeos. Ele é atualizado a cada rodada e pode ser aberto pelo app do GitHub no celular.

Os grupos, as descrições dos ganchos, os pesos e a taxa de exploração ficam no `config.yaml` e podem ser editados.

---

## Horários de publicação

| Brasília | Por quê |
|---|---|
| 07:40 | começo do dia, deslocamento |
| 12:10 | almoço |
| 18:40 | saída do trabalho |
| 21:10 | horário nobre do TikTok |

Para mudar, edite as linhas `cron` em `.github/workflows/noticias-tiktok.yml`. Elas ficam em UTC, que é **Brasília + 3 horas**. Depois de algumas semanas, a tabela "Horário de publicação" do relatório mostra quais horários rendem mais.

---

## Custos aproximados (4 vídeos por dia, cerca de 120 por mês)

| Serviço | Para quê | Custo estimado |
|---|---|---|
| API do X | ler os posts | ~US$ 0,25 por rodada (50 posts × US$ 0,005) → **~US$ 30/mês** |
| Claude (Anthropic) | pauta e roteiro | ~US$ 0,05 por rodada → **~US$ 6/mês** |
| ElevenLabs | narração | ~60 a 80 mil caracteres/mês → confira se o seu plano cobre |
| Pexels | vídeos de fundo | grátis |
| Upload-Post | publicar no TikTok | plano pago (veja o site) |
| API do TikTok | ler métricas | grátis |
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
| `PEXELS_API_KEY` | pexels.com/api (grátis). **Recomendado**: sem ela, o fundo vira uma arte animada, e vídeos de verdade prendem muito mais. |

### 2. Publicação no TikTok

**Opção A — Upload-Post (recomendada para começar).** Os vídeos saem **públicos** desde o primeiro dia, porque o app deles já é aprovado pelo TikTok.
1. Crie a conta em upload-post.com e um perfil chamado `noticias`.
2. Conecte a sua conta do TikTok a esse perfil.
3. Copie a API key para o secret `UPLOADPOST_API_KEY`.

**Opção B — API oficial do TikTok (gratuita).** Enquanto o seu app não passa pela auditoria do TikTok, **todos os vídeos ficam privados** (só você vê). Para usá-la, troque `metodo: "uploadpost"` por `metodo: "tiktok"` no `config.yaml` e siga o passo 3 com os escopos completos.

### 3. Métricas do TikTok (necessário para o aprendizado)

O aprendizado lê os números pela API oficial do TikTok, escopo `video.list`. **Isso vale mesmo para quem publica pelo Upload-Post.**
1. Em developers.tiktok.com, crie um app com **Login Kit** e cadastre uma *Redirect URI* https (pode ser qualquer endereço seu). Para a Opção B, adicione também a *Content Posting API* com *Direct Post*.
2. No seu computador, rode o script de autorização (instruções no topo de `scripts/tiktok_autorizar.py`):
   - publicando pelo Upload-Post: `--escopos user.info.basic,video.list`
   - publicando pela API oficial: deixe o padrão (`user.info.basic,video.list,video.publish`)
3. Cadastre os secrets `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` e `TIKTOK_REFRESH_TOKEN`.
4. Recomendado: o secret `GH_PAT` (token do GitHub com permissão *Secrets: write* neste repositório). O TikTok troca o refresh token de tempos em tempos, e com esse secret o robô salva o novo sozinho.

Sem esses secrets, o robô funciona normalmente e continua variando o formato, mas não aprende.

### 4. Cadastre no GitHub

No repositório: **Settings → Secrets and variables → Actions**
- Aba **Secrets**: as chaves acima.
- Aba **Variables**:
  - `ROBO_ATIVO` = `true` → liga os horários automáticos.
  - `PUBLICAR` = `false` → nos primeiros dias o robô só **gera** os vídeos, sem publicar.

> O GitHub só roda horários automáticos a partir do branch principal (`main`). Por isso o código precisa estar no `main`.

### 5. Teste

1. **Actions → Notícias TikTok → Run workflow → modo `teste`**. No campo *formato*, você pode forçar opções (ex.: `gancho=numero,musica=pulsante`).
2. Ao terminar, abra a rodada: o resumo mostra o gancho, o formato escolhido, a legenda e os posts de origem. O vídeo fica em **Artifacts**, no fim da página.

### 6. Ligue a publicação

Gostou dos vídeos de teste? Troque a variável `PUBLICAR` para `true`. Para pausar tudo, mude `ROBO_ATIVO` para `false`.

---

## Ajustes no `config.yaml`

- **canal.nome**: nome que aparece no topo do vídeo.
- **coleta.contas / minimo_fontes**: perfis monitorados e quantos veículos precisam confirmar a notícia.
- **narracao**: voz, energia e velocidade.
- **video**: cores, volumes da trilha e dos efeitos.
- **variantes**: opções testadas e as instruções de cada estilo de gancho.
- **aprendizado**: tempo até medir, mínimo de testes, exploração e pesos da nota.

## Testar no computador

```bash
cd noticias-tiktok
pip install -r requirements.txt   # e instale o FFmpeg
python -m noticias.main --demo --formato "musica=pulsante,ritmo=rapido"
```

O vídeo de exemplo é gerado em `saida/`, sem nenhuma chave, com voz muda no lugar da narração.

---

## Cuidados importantes

- **Responsabilidade pelo conteúdo.** O robô usa só veículos estabelecidos, exige confirmação por duas fontes e proíbe inventar dados. Mesmo assim, notícias mudam rápido. Acompanhe os vídeos, principalmente nas primeiras semanas, e apague qualquer erro na hora.
- **Rótulo de IA.** Os vídeos levam o rótulo "gerado por IA" do TikTok e o aviso na tela. Não remova: o TikTok exige isso para voz sintética.
- **Alcance.** O TikTok pode dar menos alcance a conteúdo que considera repetitivo. O teste contínuo de formatos ajuda. Vale também, de vez em quando, trocar a voz e as cores.
- **Direitos de imagem e som.** Nada é reaproveitado dos posts do X: as imagens vêm do banco livre do Pexels, e a trilha e os efeitos são originais.
