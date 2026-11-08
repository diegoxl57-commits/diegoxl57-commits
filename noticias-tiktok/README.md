# Robô de notícias para o TikTok

Quatro vezes por dia, o robô:

1. **Mede o que já foi ao ar**: lê no TikTok as visualizações, curtidas, comentários e compartilhamentos dos vídeos anteriores.
2. **Escolhe o formato da rodada** (gancho, duração, ritmo e trilha), priorizando o que deu mais resultado.
3. **Lê as notícias** das últimas horas nos feeds dos próprios veículos (g1, Folha, CNN Brasil, BBC Brasil, Agência Brasil, UOL, Metrópoles, Poder360, Veja, DW, InfoMoney).
4. **Escolhe a pauta e escreve**: o Claude escolhe **uma** notícia confirmada por pelo menos **2 veículos** e escreve gancho, roteiro, pergunta para comentários, legenda e hashtags.
5. **Narra** com voz neural brasileira do Google, com o tempo de cada palavra.
6. **Monta o vídeo viral** 1080×1920.
7. **Manda o vídeo para a caixa de entrada do seu TikTok** e **comenta a legenda pronta no GitHub**. Você abre, cola e publica com um toque.
8. **Atualiza o relatório** `estado/desempenho.md`.

---

## Quanto custa: só os seus créditos do Claude

| Peça | Serviço | Custo |
|---|---|---|
| Roteiro | Claude (Anthropic) | **seus créditos de API**, cerca de US$ 0,05 por vídeo |
| Notícias | RSS dos veículos | grátis |
| Voz | Google Cloud Text-to-Speech | grátis até 1 milhão de caracteres/mês (o robô usa uns 100 a 300 mil) |
| Imagens | Pexels | grátis |
| Publicação e métricas | API oficial do TikTok | grátis |
| Servidor | GitHub Actions (repositório público) | grátis |

As opções pagas continuam disponíveis no `config.yaml`, caso um dia você queira: notícias pela API do X, voz da ElevenLabs e publicação 100% automática pelo Upload-Post.

---

## O dia a dia (modo rascunho)

1. O **TikTok** te avisa que há um vídeo na caixa de entrada.
2. O **app do GitHub** te avisa com um comentário na issue *"Vídeos prontos para publicar no TikTok"*, que traz a legenda pronta e as fontes conferidas.
3. No TikTok: abra o rascunho, **cole a legenda** sem mudar o começo, ative **Conteúdo gerado por IA** em *Mais opções*, escolha um som em alta se quiser, e **publique**.

Leva uns 30 segundos por vídeo. É também a sua chance de revisar a notícia antes de ir ao ar.

---

## Configuração (pelo iPad, no Safari)

Para cadastrar cada chave, use a página **Settings → Secrets and variables → Actions** do repositório:
**Secrets** → *New repository secret*; **Variables** → *New repository variable*.
Nunca cole chaves no chat nem em arquivos.

### 1. Claude → secret `ANTHROPIC_API_KEY`
Em **platform.claude.com**, na organização que tem os seus créditos: **Settings → API Keys → Create Key**.

### 2. Voz do Google → secret `GOOGLE_TTS_API_KEY`
1. Em **console.cloud.google.com**, crie um projeto (ex.: `robo-noticias`).
2. **Faturamento**: vincule uma conta de faturamento. O Google exige cartão, mas dentro da cota grátis não cobra nada.
3. Em **APIs e serviços → Biblioteca**, procure **Cloud Text-to-Speech API** e toque em **Ativar**.
4. Em **APIs e serviços → Credenciais → Criar credenciais → Chave de API**. Depois, em **Restringir chave**, permita só a **Cloud Text-to-Speech API**.
5. Copie a chave e salve como secret.
6. **Segurança**: em **Faturamento → Orçamentos e alertas**, crie um orçamento de R$ 1 com alerta por e-mail.

### 3. Imagens → secret `PEXELS_API_KEY`
Em **pexels.com/api**, crie uma conta e peça a chave. Ela sai na hora.

### 4. TikTok: app de desenvolvedor
1. Em **developers.tiktok.com**, entre com a sua conta do TikTok e crie um app (*Manage apps → Connect an app*).
   - Nome: `Robo Noticias`. Categoria: notícias. Ícone: qualquer imagem quadrada.
   - Site, termos e privacidade: pode usar o endereço deste repositório.
2. Adicione os produtos **Login Kit** e **Content Posting API**, e também **Display API**, se aparecer.
   - No Login Kit, cadastre a *Redirect URI*: `https://github.com/diegoxl57-commits/diegoxl57-commits`
   - Permissões (*scopes*): `user.info.basic`, `video.list` e `video.upload`.
3. Ative o **Sandbox** e adicione a sua conta do TikTok como usuário de teste (*target user*).
4. Copie a **Client key** para a **variável** `TIKTOK_CLIENT_KEY` e o **Client secret** para o **secret** `TIKTOK_CLIENT_SECRET`.

### 5. Token do GitHub → secret `GH_PAT`
Ele permite que o robô guarde sozinho o acesso ao TikTok.
1. Em **github.com/settings/personal-access-tokens/new**, crie um *fine-grained token*:
   - Nome: `robo-noticias`. Validade: 1 ano.
   - Acesso: *Only select repositories* → este repositório.
   - Permissões → *Repository permissions* → **Secrets: Read and write**.
2. Gere o token e salve como secret `GH_PAT`.

### 6. Autorizar o TikTok (pelo próprio iPad)
1. **Actions → Autorizar TikTok → Run workflow**, com o campo vazio.
2. Abra a rodada: o resumo traz o link **Autorizar o robô no TikTok**. Abra o link e autorize.
3. O Safari vai abrir este repositório com `?code=...` no endereço. **Copie o endereço inteiro.**
4. Em poucos minutos, rode **Autorizar TikTok** de novo, colando o endereço no campo *retorno*. O token é salvo sozinho.

### 7. Ligar
Na aba **Variables**, crie:
- `ROBO_ATIVO` = `true` (liga os horários)
- `PUBLICAR` = `false` (primeiro só gera os vídeos, para você avaliar)

Teste em **Actions → Notícias TikTok → Run workflow → modo `teste`**. O vídeo fica em *Artifacts*, no fim da página da rodada. Quando gostar, mude `PUBLICAR` para `true`.

---

## Horários

07:40, 12:10, 18:40 e 21:10 (Brasília). Para mudar, edite as linhas `cron` em `.github/workflows/noticias-tiktok.yml`. Elas ficam em UTC, que é Brasília + 3 horas.

## O formato viral

- **0 a 2 s**: gancho gigante na tela, com som de impacto.
- **Corpo**: cortes de cena a cada 2 a 3,5 s, com zoom, flash e "whoosh". Legendas palavra por palavra: a palavra falada em amarelo, números e palavras-chave em verde.
- **Final**: pergunta para comentários com o selo "COMENTE AQUI".
- **Áudio**: trilha e efeitos originais gerados por código, sem direitos autorais. Volume no padrão das redes.
- **Regras**: o gancho é sempre verdadeiro, a notícia tem duas fontes, e nada de boato ou dado inventado.

## Aprendizado automático

Cada vídeo usa uma opção de cada grupo: gancho (pergunta, número, impacto, novidade ou contraste), duração (curto ou médio), ritmo (rápido ou normal) e trilha (pulsante, tensa ou sem). Depois de 24 h no ar, cada vídeo recebe uma nota relativa ao canal: 60% vem das visualizações e 40% da interação.

Cada opção é testada pelo menos 3 vezes. Depois, em 80% das rodadas, o robô usa a de melhor nota e, nas outras 20%, continua testando. O Claude também recebe os melhores e os piores vídeos para escolher pautas e aberturas.

O relatório fica em `estado/desempenho.md`. Para o robô reconhecer o vídeo, **cole a legenda sem alterar o começo** e publique em até 48 h.

## Ajustes no `config.yaml`

- `canal.nome`: nome no topo do vídeo.
- `coleta.rss.feeds`: veículos monitorados. Feed fora do ar é ignorado, com aviso no log.
- `narracao.google`: vozes, velocidade e tom.
- `variantes` e `aprendizado`: opções testadas e regras do teste A/B.
- `publicacao.metodo`: `tiktok_rascunho` (padrão), `tiktok` (direto, privado até a auditoria) ou `uploadpost` (pago).

## Testar no computador

```bash
cd noticias-tiktok && pip install -r requirements.txt   # e instale o FFmpeg
python -m noticias.main --demo --formato "musica=pulsante,ritmo=rapido"
```

## Cuidados

- **Responsabilidade**: confira cada notícia antes de publicar. O modo rascunho existe para isso.
- **Rótulo de IA**: ative sempre "Conteúdo gerado por IA" ao publicar. O TikTok exige isso para voz sintética.
- **Privacidade do código**: o repositório é público. As chaves ficam protegidas nos Secrets, mas o código e o histórico ficam visíveis.
