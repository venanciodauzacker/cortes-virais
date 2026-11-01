---
name: cortes-virais
description: Transforma vídeos longos do Venâncio (conversas, gravações DJI horizontais) em cortes verticais 9:16 virais, no estilo dos vídeos de referência em ~/Documents/ESTILOS DE CORTES. Acha os melhores momentos, monta no estilo "Lego" (gancho mais forte no começo), coloca legenda palavra a palavra, título e música, e sempre gera 3 ou mais variações por corte. Use quando o usuário pedir "faz cortes", "corta esse vídeo", "edita esses cortes", "cortes virais", "reels/tiktok desse vídeo", ou mandar uma pasta de vídeos brutos pra cortar.
---

# Cortes virais

Pega vídeo longo bruto e entrega vários cortes curtos, prontos pra postar.

## Ferramentas (já instaladas)
- `ffmpeg` e `whisper-cli` em `~/.local/bin`
- Modelo do Whisper: `~/tools/whisper-models/ggml-medium.bin`
- Músicas: `~/Documents/ESTILOS DE CORTES /MUSICAS PARA OS CORTES/` (o nome da pasta tem um espaço no fim)
- Referências visuais: `~/Documents/ESTILOS DE CORTES /MODELOS DE CORTES /*.mp4` (os 'alfredo 0X' e 'Alfredo acido 3' são o estilo tela dividida = `oeuvencedor` no script). A análise está em `referencias/estilos.md`; ler antes de começar.
- Scripts: `scripts/transcrever.py` e `scripts/renderizar.py` (rodar com `python3 -I`)

## Fluxo

### 1. Transcrever cada vídeo bruto
```bash
python3 -I ~/.claude/skills/cortes-virais/scripts/transcrever.py "<video>" pt
```
- Cria `<video>.cortes/transcricao.txt` (frases com tempo) e `palavras.json` (tempo de cada palavra).
- Demora mais ou menos 2x a duração do vídeo. Vídeos acima de 5 min: rodar em segundo plano e, se forem vários, transcrever um de cada vez.
- Se a pasta `.cortes` já existe, ele pula.

### 2. Achar os melhores momentos
Ler `transcricao.txt` inteiro. Procurar trechos de 20 a 90s que:
- Têm gancho forte (ver "Padrões de gancho" em `referencias/estilos.md`): frase polêmica, número ou dinheiro, conselho contrário, pergunta direta, história com virada.
- Se entendem sozinhos, sem o contexto do resto do vídeo.
- **Contexto é obrigatório (o corte tem que viralizar sozinho).** Nunca usar a estrutura do vídeo original: "vou te dar 5 conselhos", "o segundo conselho é", "último conselho", "como eu falei". Se o vídeo é uma lista, cada item vira corte próprio começando direto na ideia ("mandar mensagem pra quem tem resultado..."), e a introdução que promete a lista NÃO vira corte.
- O corte não pode começar com palavra que aponta pra algo que não está nele: "isso me fez...", "essas pessoas", "que é basicamente", "é o contrário", "nisso". Ou inclui a frase anterior que dá o sentido, ou começa depois. Ler o texto inteiro de cada corte (o `.texto.json`) antes de entregar e perguntar: quem nunca viu o vídeo entende?
- Entregam uma ideia completa: problema, virada, lição.
- Ignorar: bastidor ("tá gravando?", "vou pausar"), repetições, enrolação, conversa sobre a câmera.

Pra cada momento, anotar o tempo exato pelo `palavras.json` (início da primeira palavra e fim da última).

### 3. Montar no estilo "Lego"
O corte não precisa seguir a ordem original. Montar com peças:
1. **Gancho (1 a 4s):** a frase mais forte do trecho, mesmo que venha do meio ou do fim.
2. **Contexto:** a pergunta ou situação que leva até ela.
3. **Desenvolvimento:** a explicação, sem pausas e sem repetição.
4. **Fecho:** termina na frase de impacto ou na lição, sem despedida.

Regras de corte:
- Cortar toda pausa maior que 0,3s e todo "é...", "tipo...", "né" sobrando. Cada segmento termina no fim da palavra e o próximo começa no início da palavra seguinte.
- Alternar `zoom` entre os segmentos (1.0 → 1.2 → 1.0) pra simular troca de câmera nos jump cuts.
- `crop_x` centraliza a PESSOA, não o meio da câmera. Calcular por trecho detectando o rosto (OpenCV Haar, ver `CORTES PRONTOS/dji-28-10/planos/gerar.py`, função `rosto_x`; rodar o gerador com `python3` sem `-I`, porque o cv2 está no site do usuário). Conferir com um frame.
- Vídeo VERTICAL de celular: o script detecta sozinho e usa a largura inteira, cortando só a altura no meio. NÃO dar zoom (zoom sempre 1.0), NÃO mexer no ângulo (`crop_y`) e NÃO mexer na cor (`cor`): o usuário rejeitou isso em 28/10 ("deixa a coloração original, sem zoom, só bota a divisão").
- Corte "completo" = a fala inteira NA ORDEM ORIGINAL, sem trazer trecho do fim pra frente. Um por modelo pedido (ex.: 1 tino + 1 tela dividida). As outras variações podem brincar com ordem e tamanho.
- Print/thumb de podcast ou referência citada na fala: `cobertura` no segmento da citação (Tino) ou `imagem_inferior` (tela dividida). Thumbs do YouTube: `i.ytimg.com/vi/<id>/maxresdefault.jpg`, salvar em `FOTOS PARA CORTE/<assunto>/`.
- Duração final: proporção obrigatória em todo lote, sem o usuário pedir:
  - **60% curtos:** abaixo de 40s (20 a 39s).
  - **40% longos:** ACIMA de 40s (41s a 1m30). Bloco inteiro de um assunto (um conselho, uma história completa), com poucas emendas.
  - Conferir a conta antes de renderizar (ex.: 50 cortes = 30 curtos + 20 longos). Os longos também variam de modelo e de montagem, como os curtos.

### 4. Variações (obrigatório)
Objetivo: o MÁXIMO de cortes por vídeo, sempre com contexto. Pra CADA momento escolhido, gerar 3 a 4 versões (uma por modelo: henrico, tino, tela dividida, alfredo), cada uma com uma montagem de fala diferente (Lego: outro gancho, outra ordem, outro recorte) (ver "Variação é fala diferente"):
- O estilo `tino` é o principal: muitas variações, incluindo cortes COMPLETOS (a fala inteira, 1m30+) com ganchos diferentes. Pelo menos metade das variações de um lote usa ele, sempre com 💀 no título; mitada só se a fala tiver momento forte (ver "Mitada").
- **V1:** gancho A + estilo `tino` + música 1
- **V2:** gancho B (outra frase do trecho no começo) + estilo `banner` + título diferente + música 2
- **V3:** ordem original ou outro recorte + estilo `vlog` + título diferente + música 3
Também dá pra variar: comprimento (curto de 20s e longo de 50s), cor da legenda, 1 ou 2 palavras por legenda, ponto de início da música. Nunca repetir a mesma combinação de gancho, estilo, título e música.

Quando dois momentos falam a mesma coisa com palavras diferentes, cada um vira um corte separado, com as suas 3 variações. O objetivo é volume.

### 4b. Variação "o vídeo todo num short" (obrigatória quando o vídeo é uma lista)
Se o vídeo tem estrutura de lista (5 conselhos, 3 erros, os passos de...), montar um short que resume o vídeo inteiro: o gancho da introdução ("vou te dar 5 conselhos...", o resultado: "Rolex com 20 anos") + SÓ a frase-resumo de cada item, em ordem ("o primeiro conselho vai ser estudar lançamentos", "o segundo é mandar mensagem pra quem tem resultado"...), cada uma com `"rotulo": "CONSELHO 1"` no segmento (caixa amarela que entra com pop; segmentos seguidos com o mesmo rótulo continuam a mesma caixa). Fecha numa frase de impacto (ex.: "isso me fez chegar até aqui, na Suécia").
- Fazer em todos os modelos, com montagens diferentes: introdução + itens; resultado primeiro + introdução + itens; só os itens.
- É aqui que a introdução da lista pode entrar, porque o corte entrega todos os itens que ela promete.
- Pensar no mesmo espírito em qualquer vídeo: frases soltas ao longo do vídeo que, juntas, contam a ideia toda em 30s.

### 5. Escrever o plano e renderizar
Um JSON por variação. Salvar os planos junto dos cortes, em `<pasta do bruto>/CORTES PRONTOS/planos/`.
```json
{
  "saida": "<pasta do bruto>/CORTES PRONTOS/01-sapo_v1_podcast.mp4",
  "estilo": "podcast",
  "titulo": "Faça *isso* no começo do dia\nse quer faturar previsível",
  "handle": "@venancio",
  "cor_legenda": "amarelo",
  "palavras_por_legenda": 1,
  "musica": "acido",
  "musica_inicio": 20,
  "volume_musica": 0.12,
  "crop_x": 0.58,
  "segmentos": [
    {"fonte": "/caminho/bruto.MOV", "inicio": 54.5, "fim": 56.95, "zoom": 1.25},
    {"fonte": "/caminho/bruto.MOV", "inicio": 14.8, "fim": 22.0}
  ]
}
```
- `estilo`: `tino` (padrão principal: vídeo grande quase quadrado, título branco com 💀, legenda branca minúscula de 2 palavras), `podcast` (fundo preto, vídeo 4:3 no meio, legenda amarela), `banner` (tela dividida com faixa vermelha) ou `vlog` (tela cheia).
- `emoji_titulo`: emoji colado no fim do título. Opções: `caveira` (💀, padrão do tino), `caveira2` (☠️, combina com o banner), `risada`, `choque`, `fogo`, `vergonha`.
- `mitada: true` (ou `caveira: true`) num segmento: no fim dele, a imagem congela em preto e branco por 1,6s, com 💀 no lugar da legenda e um som de impacto. É a "mitada" do Tino. Não existe mitada automática: só marcar onde a fala tem algo bacana de verdade (ver "Mitada").
- `cobertura` num segmento: caminho de uma imagem ou vídeo que cobre a imagem enquanto o áudio continua. O Tino usa isso na pergunta inicial (foto do Ronaldo, da fila do iPhone). Usar só se o usuário mandar b-roll ou se existir um arquivo adequado.
- `titulo`: `\n` quebra a linha; `*palavra*` fica amarela. No banner vira caixa alta sozinho.
- `musica`: parte do nome do arquivo. `""` = sem música.
- `imagem_inferior` (só banner): foto pra metade de baixo. SEMPRE usar: nunca deixar o plano aberto do mesmo vídeo embaixo (a mesma pessoa em cima e embaixo não faz sentido). Foto do Venâncio ou imagem ligada ao assunto (venda, dinheiro, viagem).
- `segmentos` podem misturar vídeos brutos diferentes.
- `inicio_exato` / `fim_exato` num segmento: corta exatamente nesse tempo, sem o ajuste automático. Usar quando a transcrição geral erra o trecho (fala travada, repetição): achar o ponto testando o trecho com `whisper-cli` em pedaços curtos. Se a legenda sair errada, corrigir as palavras em `palavras.json` (guardar o original em `palavras.orig.json`).

```bash
python3 -I ~/.claude/skills/cortes-virais/scripts/renderizar.py "<plano.json>"
```
Cada corte leva de 2 a 4 min (cortes acima de 60s levam até 15 min). Vários de uma vez: rodar em segundo plano, num loop, UM DE CADA VEZ.
- Nunca rodar dois whisper ao mesmo tempo (render, revisar ou teste): a GPU trava, os processos ficam presos em estado UN e a fila para. Testes de emenda durante a fila: esperar a fila acabar.
- Limite por corte no loop: `perl -e 'alarm 1500; exec @ARGV'` (o macOS não tem `timeout`). 600s mata os cortes longos.
- Depois de cada corte, `pkill -9 whisper-cli` pra não sobrar processo órfão.
- Se travar: `pkill -9 whisper-cli`, testar um trecho de 8s (tem que levar ~6s na GPU) e só então religar.

### 6. Conferir antes de entregar
- Tirar 1 frame de cada corte (`ffmpeg -ss 3 -i corte.mp4 -frames:v 1 f.jpg`) e olhar: rosto enquadrado, título sem cortar, legenda legível.
- Se o enquadramento estiver ruim, ajustar `crop_x` ou `zoom` e renderizar de novo.
- Transcrever o corte pronto de novo e comparar com o plano: emenda cortando palavra no meio ou frase sem sentido = refazer o segmento.
- Alerta do `revisar.py` com 'entendeu?', 'sacou', 'porque' inteiros na emenda costuma ser fala real que a transcrição geral pulou: não é defeito. Pedaço de palavra ('que cara' sobrando antes do começo, 'Ai,') é vazamento: começar o segmento na frase inteira (ex.: 'A real é que, cara, é muito difícil') com `inicio_exato` medido pela energia do áudio.
- Entregar uma tabela: arquivo | gancho (primeira frase) | estilo | título | duração.

### 7. Preparar pra postar
No fim, gerar `CORTES PRONTOS/agenda-hoje.json` com uma linha por corte: `{"n", "arquivo", "titulo", "hora"}`.
- `titulo`: o título do corte numa linha só, sem `*`, sem `\n` e sem emoji. Vira a legenda.
- Não repetir título entre posts. Variações do mesmo trecho ficam espaçadas (nunca seguidas).
- Daí é só rodar a skill `agendar-meta`.

## Modelo Henrico (`"estilo": "henrico"`)
Referência: `MODELOS DE CORTES /enrico.delafiori_DQ2x4ZsADkz.mp4`. Fundo preto, vídeo 16:9 inteiro numa caixa de canto arredondado no meio da tela, SEM título no topo. Gancho (primeiro segmento, até 6s): 3 palavras grandes empilhadas do lado do rosto, a do meio amarela. Depois: legenda pequena, minúscula, 2 palavras, no canto de cima à esquerda da caixa. Combina com vídeo horizontal (câmera fixa) e pessoa no meio/direita do quadro. O `titulo` do plano não aparece no vídeo, só vira legenda do post. Sem mitada.

## Cor
Quando o usuário pedir "mais cor": `"cor": "henrico"` no plano (leve: um pouco mais quente e saturado, aprovado em 29/10). Não usar o grade escuro/laranja do Enrico inteiro nem nada mais forte que isso. Sem pedido, não mexer na cor.

## Henrico pro (`scripts/henrico_pro.py`)
Versão caprichada do modelo Henrico, modelada nos 3 vídeos do Enrico: legenda com motion feita no Remotion (`motion/src/Legendas.tsx`), parte do texto atrás do corpo inteiro e parte na frente, fotos do banco entrando na caixa com a palavra no meio.
1. Renderizar a base com `"estilo": "henrico", "sem_legenda": true`.
2. Quadros da caixa: `ffmpeg -i base.mp4 -vf crop=912:513:84:703 q/%05d.jpg`.
3. Máscara da pessoa: `scripts/mascara/mascara q m` (Vision da Apple, já compilado; o Swift do Mac está quebrado, por isso é Objective-C).
4. Camadas: gancho, frases do lado da cabeça e destaques (gigantes, amarelos, encostados na cabeça) passam ATRÁS do corpo inteiro (máscara `m`); palavras grandes do peito ficam NA FRENTE de tudo. Nunca usar máscara só de cabeça: o texto parece cortado no pescoço (o usuário reprovou).
5. Plano pro (`base`, `mascaras`: m, `saida`, `destaques`, `riscar`, `fotos`) e `python3 -I scripts/henrico_pro.py plano.json` (`"teste": 10` faz prévia curta).
Legenda (como o Enrico): gancho em bloco colado à esquerda (2ª palavra itálico sublinhado, palavra curta pequena, a final grande que fica amarela e troca pra fonte condensada); frase curta = uma palavra grande por vez no peito; frase longa = linhas pequenas do lado da cabeça que entram cinza, ficam brancas e saem desfocando.
Música: "yara yara ya" é a do Enrico, mas não ficou boa em corte longo; nos longos usar outra do rodízio.

## Cortes longos (estilo Alfredo)
Fazem parte de todo lote (40% dos cortes, ver seção 3): 41s a 1m30, principalmente no estilo `oeuvencedor` (tela dividida, faixa vermelha), mas também em henrico, tino e alfredo; trechos corridos com poucas emendas, mitada só no tino, música no mesmo rodízio de todas as músicas da pasta, sempre do início. Foto embaixo só quando quem fala é o Venâncio sem pergunta de outra pessoa.

## Músicas disponíveis
| Arquivo | Duração |
|---|---|
| 180db 130 Intro Slowed.mp3 | 2:28 |
| IMPXSTR GALAXY!.mp3 | 1:10 |
| Lorn Acid Rain.mp3 | 2:52 |
| Triumph.mp4 | 2:15 |
| usar mais acido 3 Slowed.mp3 | 1:48 |
| bad parenting v2.mp3 | 1:30 |
| dia de fiesta slowed.mp3 | 2:00 |
| rvkn crusader slowed.mp3 | 2:49 |
| yara yara ya .mp4 | 3:26 |

**Usar TODAS as músicas da pasta, em rodízio.** Listar a pasta no começo de cada lote (o usuário pode adicionar músicas) e distribuir igual: corte 1 música 1, corte 2 música 2... e volta pro começo. Nenhuma música repetida em cortes seguidos. A 'acido 3' entra no rodízio como as outras (o usuário reclamou quando 22 de 32 cortes usaram ela).
**Sempre do início da música:** `musica_inicio` = 0 (ou 0.5 nas que começam com meio segundo de silêncio: IMPXSTR, Lorn, Triumph, rvkn). Nenhum corte sem música: antes de renderizar, conferir que todo plano tem `musica` que bate com um arquivo da pasta. Volume entre 0.08 e 0.15, sem cobrir a voz.
Nenhum estilo termina com imagem congelada: o usuário acha que parece travado. A única pausa congelada permitida é a mitada do Tino.

## Títulos (headline)
Todo corte tem um título DIFERENTE, mesmo quando é variação do mesmo trecho. Nada de repetir a mesma frase com outras palavras.
- Formato: 2 linhas; a primeira traz a pergunta ou o contexto, a segunda a conclusão provocativa.
- Busque o ângulo polêmico: atacar uma crença ("Ter plano B é coisa de quem já aceitou perder"), comparar com status ("Seu professor ganha menos que esse moleque"), apontar o dedo pro espectador ("Você não está atrasado. Você está com medo"), número concreto ("O professor deu zero. O mercado deu 20 mil por mês").
- Por variação, use um ângulo diferente: crença atacada, comparação, dor do espectador, número/resultado, conselho contrário.
- Tino: frase normal com 💀. jon: Cada Palavra Com Maiúscula e 😱😱. alfredo/oeuvencedor: *destaque* em amarelo.

## Fotos (banco de imagens)
`~/Documents/ESTILOS DE CORTES /FOTOS PARA CORTE/nomeadas/` tem as fotos do Venâncio nomeadas pelo conteúdo (ver `CATALOGO.md`).
- NUNCA colocar foto por cima do vídeo nos cortes.
- Foto só como `imagem_inferior` no modelo oeuvencedor (tela dividida, foto presa embaixo), e só quando quem fala no corte é o Venâncio (as fotos são dele). Corte de convidado (ex.: João) fica com o plano aberto embaixo.

## Mitada (com moderação)
- Só no modelo Tino. Os outros modelos (alfredo, oeuvencedor, jon) não levam mitada.
- Ser modelo Tino NÃO obriga a ter mitada. Se a fala não tem um momento forte, o corte sai sem nenhuma.
- Quando tem: no máximo UMA, logo depois de frase realmente forte (número absurdo, flex tipo Rolex, frase polêmica seca, piada, "morreria tentando"). Frase inspiracional, conselho ou explicação não leva. Na dúvida, não coloque.
- Frase de efeito seca, do tipo bordão, conta como forte e leva: "quem é bom em dar desculpa não é bom em mais nada", "a batata aparece na sua mão", "eu faço esses 100 mil reais", "eu honrei a minha palavra". Vídeo de princípios/mentalidade costuma ter uma dessas em quase todo corte Tino: achar a CERTA e pôr a mitada logo depois dela (o usuário pediu a mitada certa, não mais mitadas).

## Variação é fala diferente, não só edição diferente
- Cada corte do mesmo vídeo monta uma FALA diferente: outro gancho, outros trechos, ordem Lego diferente, às vezes um pedaço do meio puxado pra frente ou um trecho de outra parte do vídeo. Não basta trocar o estilo de edição em cima da mesma montagem.
- Misturar comprimentos: curtos, médios e longos (completo pode passar de 1m30). O objetivo é viralizar: o tamanho vem do que a fala segura de atenção, NÃO da minutagem dos vídeos de referência (eles servem só pro estilo visual).
- Quando o usuário fala "Alfredo", ele quer dizer a TELA DIVIDIDA (`oeuvencedor` no script, referências 'alfredo 0X' e 'Alfredo acido 3'), não o estilo `alfredo` de fundo preto. É o modelo com mais referências e o que mais deve ser explorado: a maioria dos cortes do lote, cada um com fala e foto diferentes.

## Cor (vídeo HDR do iPhone)
O `renderizar.py` detecta vídeo HDR (HLG/PQ) e converte pra SDR com tonemap. Sem isso a cor sai lavada, quase preto e branco. Se aparecer vídeo acinzentado, conferir se o ffmpeg reconhece a fonte como HDR.

## Cortes validados
Corte que o usuário validou não se mexe: não renderizar de novo, não trocar título, não aplicar ajuste novo. Mudança global só vale pros cortes novos. Plano validado leva `"titulo_fixo": true`.

## Tom
Títulos em português direto, sem clickbait mentiroso: prometer só o que o corte entrega. Para o projeto Heidy (espanhol), transcrever com `es` e escrever o título em espanhol.
