# Volkswagen × Pantera Robótica — pacote de produção

Entrega final prevista: `Volkswagen_Pantera_Transformacao_Cinematografica.mp4`
(10 s, 1080 × 1920, 24 fps, H.264 High, yuv420p, BT.709, áudio AAC 48 kHz estéreo).

## Status

| Etapa | Situação |
|---|---|
| A — Preparação (plate 9:16, máscara, análise) | **Concluída** |
| B — Quadro inicial (pantera no lugar do carro) | **Bloqueada**: precisa de um modelo de edição de imagem por IA |
| C — Animação (transformação com quadro inicial/final) | **Bloqueada**: precisa de um gerador de vídeo por IA |
| D — Pós-produção (alinhamento, travamento da garagem, cor, registro final, mux) | **Pronta e testada** (`pos_producao.py`) |
| Áudio (desenho de som sincronizado) | **Concluído** (`audio_sound_design.wav`) |
| E — Controle de qualidade | Automatizado no `pos_producao.py` (folha de QC + métricas) |

Bloqueios encontrados no ambiente (verificados, não presumidos):

- **Figma Weave** (modelos Veo, Kling etc. via MCP): conta Figma não vinculada ao Weave.
  Para resolver: <https://app.weavy.ai/settings?section=profile> → vincular conta Figma.
  O uso consome créditos Weave; o custo é cotado pela ferramenta antes de cada execução.
- **huggingface.co** (modelos abertos gratuitos): bloqueado pela política de rede do ambiente.
- Credenciais GCP/AWS do contêiner: inválidas (sem Vertex AI/Veo nem Bedrock).
- Sem GPU e sem Blender; um carro 3D fiel ao Virtus da foto não existe localmente.
- `generate_image` do Figma existe, mas é pago (créditos Figma AI, sem cotação prévia) e só gera imagens.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `preparar_plate.sh` | Gera `plate_final_1080x1920.png` a partir da foto (remove as barras pretas: recorte 1204×2140 em x=1, y=238 → 1080×1920; a área útil da foto já é 9:16, então nada do cenário ou do carro é cortado) |
| `mascara_preservacao_garagem.png` | Branco = zona de ação (volume do carro + margem para cabeça/cauda/sombras, y 560–1380, borda suavizada σ=45 px); preto = garagem travada na foto |
| `audio_sound_design.wav` / `sound_design.py` | Som procedural de 10 s (−13,4 LUFS, pico −1 dBFS) |
| `pos_producao.py` | Pós-produção + QC |

A foto original e o plate **não** estão no repositório (repositório público; a placa do carro aparece).

## Etapa B — Quadro inicial (edição de imagem)

Entrada: `plate_final_1080x1920.png`. Modelos indicados: Nano Banana / Gemini Image, FLUX Kontext, GPT Image.

```
Edit this photo. Replace ONLY the grey Volkswagen sedan with a hyper-realistic giant quadruped
robotic panther built from articulated dark graphite metal armor plates, visible servo joints,
hydraulic pistons and fine panel seams, subtle cold blue-white sensor eyes. The panther occupies
exactly the same footprint and volume as the car: body spanning from the car's rear wheel to its
front bumper, shoulders at the car's roofline, head where the front grille and headlights are,
facing the camera at the same three-quarter front angle. Front paws where the front wheels were,
rear paws where the rear wheels were, all four paws planted on the concrete with soft contact
shadows matching the overhead fluorescent lighting; the metal reflects the red ceiling pipes and
fluorescent tubes. Keep everything else pixel-identical: camera position, lens, framing, red
ceiling pipes, fluorescent fixtures, green and red parking indicator lights, concrete ceiling and
floor, yellow painted floor lines, orange and white wall band, columns, color temperature and
grain. Photorealistic, same photograph. No text, no watermark.
```

Aceite do quadro inicial: garagem idêntica (comparar com o plate fora da máscara), patas exatamente
sobre as posições das rodas, cabeça na posição da grade. Gerar 2–4 variações e escolher.

## Etapa C — Vídeo (quadro inicial = pantera, quadro final = plate)

Modelo preferencial: **Kling (start + end frame, 10 s, modo pro/1080p)**. Alternativa: **Veo 3.1
(first + last frame, 8 s, com áudio nativo)**, depois `--ajustar-duracao`, ou encadeamento abaixo.
Proporção 9:16, câmera fixa, sem "camera motion".

Prompt:

```
Single continuous locked-off shot, hyper-realistic sci-fi feature film VFX, vertical 9:16, inside
the same covered parking garage. The camera does not move.
0-2s: a dark graphite robotic panther stands where the car will be, subtle breathing of internal
mechanisms, a small head turn.
2-4s: it takes one or two slow, controlled steps in place and lowers its body; internal gears begin
turning.
4-7.5s: continuous rigid mechanical transformation, piece by piece, no cuts: the front legs fold and
their mechanisms rotate into the front wheels; the rear legs fold into the rear wheels with the
exact original black-and-silver multi-spoke wheel design; the torso expands through rigid hinged
panels; metal plates slide and lock to form the doors and fenders; the head reorganizes into the
front grille, hood and LED headlights of the Volkswagen; the roof and windows slot into place; the
tail retracts into the rear; every part locks with a solid mechanical clunk.
7.5-10s: the finished grey metallic Volkswagen sedan sits perfectly still in the parking space,
identical to the reference photo: same paint, wheels, headlights, emblems, proportions and position.
Rigid metal parts with physically plausible motion, ease-in and ease-out, natural reflections of the
fluorescent lights, consistent contact shadows on the concrete. Background, lighting and
architecture stay completely unchanged throughout.
Audio: quiet parking garage ambience, servo whirs, hydraulic hisses, metallic clicks and heavy
locking clunks synchronized with the transformation. No dialogue, no music.
```

Negative prompt:

```
morphing, melting, liquid metal, dissolve, crossfade, fade, flash, glow burst, cut, jump cut,
camera shake, camera movement, zoom, scene change, street, outdoors, rain, different car model,
different wheels, extra wheels, distorted wheels, changed paint color, changed headlights, changed
grille, objects appearing from nowhere, flicker, warping background, text, subtitles, watermark,
cartoon, low detail
```

### Plano B — quadros-chave guiados (se o clipe único derreter/morfar)

1. Gerar o quadro-chave **K5** (t = 5 s) por edição de imagem, usando o quadro inicial e o plate
   como referências: patas dianteiras já dobradas em rodas dianteiras (desenho original), patas
   traseiras começando a dobrar, tronco ainda felino, cabeça intacta.
2. Segmento 1: início → K5 (5 s). Segmento 2: K5 → plate (5 s).
3. Os segmentos compartilham o quadro K5, então a geometria é contínua; para evitar "tranco" de
   velocidade na junção, descrever movimento lento em torno de K5 nos dois prompts.
4. Concatenar sem transição (`ffmpeg -f concat`), descartando o quadro duplicado, e passar pelo
   `pos_producao.py`.

## Etapa D — Pós-produção

```
python3 -I pos_producao.py --gerado clipe_gerado.mp4 \
  --plate plate_final_1080x1920.png --mascara mascara_preservacao_garagem.png \
  --audio audio_sound_design.wav \
  --saida Volkswagen_Pantera_Transformacao_Cinematografica.mp4
```

Por quadro: conformação 1080×1920 / 24 fps → alinhamento ECC euclidiano ao plate (medido só na
área travada, suavizado em 5 quadros) → ganho de cor da zona de ação ajustado ao plate →
composição com a garagem original fora da máscara → nos últimos 6 quadros (0,25 s) o resíduo do
carro gerado converge ao carro da foto, de modo que o último quadro é a própria foto. Isso corrige
diferenças finas de geometria e cor de um carro **já formado**; não substitui a transformação.
Sem interpolação de quadros por padrão (`--ajustar-duracao` só reescala o tempo).

Saídas de QC: `<saida>_qc.jpg` (quadros em 0, 2, 4, 5, 6, 7,5 e 10 s + foto) e `<saida>_qc.json`
(convergência do alinhamento, deriva corrigida, erro de costura, flicker, PSNR do quadro final e do
quadro antes do registro).

Teste técnico do pipeline (clipe sintético 720×1280 / 30 fps / 8 s com deriva de câmera de até
31 px, flicker e ruído): ECC convergiu em 240/240 quadros, deriva de 31,2 px detectada e corrigida,
saída 1080×1920 / 24 fps / 10,000 s, H.264 High + AAC, último quadro idêntico à foto.

## Áudio — mapa de eventos (`sound_design.py`)

| Tempo | Evento | Pan |
|---|---|---|
| 0–10 s | Ambiente: rumble grave, zumbido de fluorescente 120 Hz (rede 60 Hz), ar; reverb de concreto RT60 ≈ 2,3 s | — |
| 0,25–1,9 s | "Respiração" de servo, sopros hidráulicos, giro curto da cabeça | centro/dir. |
| 2,40 / 2,95 s | Dois passos metálicos (impacto grave + ressonância modal + arrasto no concreto) | dir. / esq. |
| 3,3–4,0 s | Corpo abaixa: hidráulica + servo descendente + catraca sutil | centro |
| 4,0–5,0 s | Patas dianteiras → rodas dianteiras (servo, catraca, giro, travas 4,55 / 4,97 s) | direita |
| 4,85–5,35 s | Patas traseiras → rodas traseiras (trava 5,35 s) | esquerda |
| 5,3–5,85 s | Tronco expande (hidráulica grave, rangido, travas 5,60 / 5,85 s) | centro |
| 5,75–6,4 s | Placas deslizam → portas e para-lamas (3 deslizamentos + cliques) | esq. → dir. |
| 6,25–6,8 s | Cabeça → grade, capô, faróis (catraca rápida, travas 6,55 / 6,80 s) | direita |
| 6,75–7,05 s | Teto e vidros (deslize, ticks de vidro) | centro |
| 7,0–7,32 s | Cauda recolhe (servo descendente, trava) | esquerda |
| 7,38 / 7,44 / 7,50 s | Travamentos finais (o último é o mais pesado) | centro |
| 7,62–8,6 s | Suspensão assenta, faróis acendem (relé + chirp), alívio hidráulico | centro/dir. |
