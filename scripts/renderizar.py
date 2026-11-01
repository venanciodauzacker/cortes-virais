#!/usr/bin/env python3
"""Monta um corte vertical 1080x1920 a partir de um plano JSON, imitando as referências.

Uso: python3 renderizar.py <plano.json>

{
  "saida": "/caminho/corte.mp4",
  "estilo": "tino" | "alfredo" | "oeuvencedor" | "jon",
  "titulo": "Linha de cima\\nlinha de baixo com *destaque*",   (*x* = amarelo; só alfredo/oeuvencedor)
  "emoji_titulo": "caveira",        (ver assets/emoji; "" = sem; "choque,choque" = dois)
  "musica": "bad parenting", "musica_inicio": 0,
  "imagem_inferior": "/foto.jpg",   (oeuvencedor: foto da metade de baixo)
  "crop_x": 0.5,
  "segmentos": [
    {"fonte": "/bruto.MOV", "inicio": 12.3, "fim": 20.1, "zoom": 1.0, "crop_x": 0.6,
     "cobertura": "/broll.jpg",      (imagem/vídeo no lugar da câmera, áudio continua)
     "mitada": true}                 (congela P&B + emoji + som da mitada no fim do segmento)
  ]
}
Medidas tiradas das referências em ~/Documents/ESTILOS DE CORTES (ver referencias/estilos.md).
"""
import json, os, re, shutil, subprocess, sys, tempfile, unicodedata

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTES = os.path.join(SKILL, "fonts")
EMOJI = os.path.join(SKILL, "assets", "emoji")
SOM_MITADA = os.path.join(SKILL, "assets", "mitada.wav")
FOTOS = os.path.expanduser("~/Documents/ESTILOS DE CORTES /FOTOS PARA CORTE/nomeadas")
MODELO = os.path.expanduser("~/tools/whisper-models/ggml-medium.bin")
MUSICAS = os.path.expanduser("~/Documents/ESTILOS DE CORTES /MUSICAS PARA OS CORTES")
W, H, FPS = 1080, 1920, 30
HANDLE = "@venanciodauzacker"
IDIOMA = "pt"

BRANCO, PRETO, AMARELO = "&H00FFFFFF", "&H00000000", "&H0000F5FF"

ALIAS = {"podcast": "alfredo", "banner": "oeuvencedor", "vlog": "jon"}

# Cada estilo: área do vídeo, fontes e posições medidas nas referências (em 1080x1920)
E = {
    "tino": dict(
        video=(0, 472, W, 974),  # x, y, w, h
        titulo=dict(fonte="CV TikTok Semi", tam=79, cor=BRANCO, contorno=0, sombra=2,
                    linhas_y=(361, 423)),
        leg=dict(fonte="CV TikTok Semi", tam=79, cor=BRANCO, contorno=2.2, sombra=1.5,
                 y=1300, palavras=2, caixa="min", blur=0.6),
        emoji_mitada="caveira", dur_mitada=1.8, mitada_pb=True, mitada_congela=True,
        handle=False, cauda=0.0, emoji_padrao="caveira", destaque=False),
    "alfredo": dict(
        video=(0, 472, W, 974),
        titulo=dict(fonte="CV Montserrat Medium", tam=85, cor=BRANCO, contorno=0, sombra=0,
                    linhas_y=(320, 378)),
        leg=dict(fonte="CV Poppins Bold", tam=156, cor=AMARELO, contorno=4, sombra=0,
                 y=1330, palavras=1, caixa="min", blur=0),
        emoji_mitada="caveira", dur_mitada=1.6, mitada_pb=True, mitada_congela=True,
        handle=True, handle_y=1796, cauda=0.0, emoji_padrao="", destaque=True),
    "oeuvencedor": dict(
        video=(0, 0, W, 900), baixo=(0, 900, W, 1020),
        titulo=dict(fonte="CV Bangers", tam=122, cor=BRANCO, contorno=4, sombra=3,
                    linhas_y=(862, 930), caixa_vermelha=True),
        leg=dict(fonte="CV Bangers", tam=155, cor=BRANCO, contorno=5, sombra=3,
                 y=730, palavras=1, caixa="mai", blur=0),
        emoji_mitada="caveira2", dur_mitada=1.5, mitada_pb=False, mitada_congela=True,
        handle=False, cauda=0.0, emoji_padrao="caveira2", destaque=True),
    # enrico.delafiori: fundo preto, vídeo 16:9 numa caixa de canto arredondado no meio, sem título.
    # Gancho com palavras grandes empilhadas do lado do rosto; depois legenda pequena no canto de cima.
    "henrico": dict(
        video=(84, 703, 912, 513), raio=34, sem_titulo=True,
        titulo=dict(fonte="CV Montserrat ExtraBold", tam=60, cor=BRANCO, contorno=0, sombra=0,
                    linhas_y=(300, 360)),
        leg=dict(fonte="CV Montserrat ExtraBold", tam=60, cor=BRANCO, contorno=0, sombra=0,
                 y=0, palavras=2, caixa="min", blur=0, modo="henrico", tam_gancho=112, tam_palavra=100),
        emoji_mitada="caveira", dur_mitada=1.6, mitada_pb=True, mitada_congela=True,
        handle=False, cauda=0.0, emoji_padrao="", destaque=False),
    "jon": dict(
        video=(0, 421, W, 1076),
        titulo=dict(fonte="CV Poppins ExtraBold", tam=90, cor=BRANCO, contorno=0, sombra=2,
                    linhas_y=(329, 384)),
        leg=dict(fonte="CV Poppins ExtraBold", tam=134, cor=BRANCO, contorno=0, sombra=0,
                 y=1370, palavras=1, caixa="mai", blur=0, brilho=True),
        emoji_mitada="explodindo", dur_mitada=1.8, mitada_pb=True, mitada_congela=True,
        handle=False, cauda=0.0, emoji_padrao="choque,choque", destaque=False),
}


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ffmpeg falhou:\n" + " ".join(cmd)[:300] + "\n" + r.stderr[-2000:])
    return r.stderr


def duracao(path):
    r = subprocess.run(["ffmpeg", "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


# ---------- cortes no silêncio ----------

def energia(fonte, ini, fim):
    """RMS em janelas de 10 ms entre ini e fim (lista de (t, rms))."""
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{max(0, ini):.3f}", "-t", f"{fim - ini:.3f}",
                        "-i", fonte, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True)
    a = r.stdout
    n = len(a) // 2
    vals = [int.from_bytes(a[i * 2:i * 2 + 2], "little", signed=True) for i in range(n)]
    out = []
    for k in range(0, n - 160, 160):
        bloco = vals[k:k + 160]
        out.append((max(0, ini) + k / 16000, (sum(v * v for v in bloco) / 160) ** 0.5))
    return out


def suavizar(jan, k=3):
    vs = [v for _, v in jan]
    return [(jan[i][0], sum(vs[max(0, i - k):i + k + 1]) / len(vs[max(0, i - k):i + k + 1]))
            for i in range(len(vs))]


def norm(w):
    w = unicodedata.normalize("NFD", w.lower())
    return re.sub(r"[^a-z0-9%]", "", "".join(c for c in w if unicodedata.category(c) != "Mn"))


def palavras_locais(fonte, a, b):
    """Transcreve só [a, b] com alinhamento DTW. Em trecho curto o tempo de cada
    palavra fica preciso (no arquivo inteiro erra até ~0,4s)."""
    tmp = tempfile.mkdtemp()
    wav = os.path.join(tmp, "l.wav")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{max(0, a):.3f}", "-t", f"{b - a:.3f}", "-i", fonte,
                    "-ar", "16000", "-ac", "1", wav], check=True)
    subprocess.run(["whisper-cli", "-m", MODELO, "-l", IDIOMA, "-f", wav, "-dtw", "medium", "-nfa", "-ojf",
                    "-of", os.path.join(tmp, "l")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    try:
        segs = json.load(open(os.path.join(tmp, "l.json"), encoding="utf-8", errors="replace"))["transcription"]
    except (OSError, ValueError):
        return []
    out, ant = [], 0.0
    for s in segs:
        for tk in s["tokens"]:
            tx, td = tk["text"], tk.get("t_dtw", -1)
            if tx.startswith("[") or tx.startswith("<|") or td < 0:
                continue
            t = td / 100
            if tx.startswith(" ") or not out:
                out.append({"w": tx.strip(), "s": ant + max(0, a), "e": t + max(0, a)})
            else:
                out[-1]["w"] += tx
                out[-1]["e"] = t + max(0, a)
            ant = t
    shutil.rmtree(tmp)
    for p in out:  # palavra que "engoliu" fala não reconhecida: início plausível pelo tamanho
        maxdur = 0.12 + 0.075 * len(p["w"])
        if p["e"] - p["s"] > maxdur:
            p["s"] = p["e"] - maxdur
    return [p for p in out if norm(p["w"])]


def achar_local(globais, locais, alvo_idx, t_alvo):
    """Acha no trecho local a mesma palavra do índice global, casando 3 palavras de contexto."""
    ctx = [norm(p["w"]) for p in globais[max(0, alvo_idx - 2):alvo_idx + 1]]
    melhor, nota = None, -1
    for i, p in enumerate(locais):
        loc = [norm(x["w"]) for x in locais[max(0, i - len(ctx) + 1):i + 1]]
        n = sum(1 for x, y in zip(reversed(ctx), reversed(loc)) if x == y)
        if n > nota or (n == nota and melhor is not None and abs(p["s"] - t_alvo) < abs(locais[melhor]["s"] - t_alvo)):
            melhor, nota = i, n
    return melhor if nota >= 1 else None


def alinhar(glob, loc, dur):
    """Texto de 'glob' com os tempos de 'loc' (casando palavra a palavra); o que não casar
    é interpolado entre os vizinhos."""
    import difflib
    out = [{"w": g["w"], "s": None, "e": None} for g in glob]
    sm = difflib.SequenceMatcher(None, [norm(g["w"]) for g in glob], [norm(x["w"]) for x in loc], autojunk=False)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            out[a + k]["s"], out[a + k]["e"] = loc[b + k]["s"], loc[b + k]["e"]
    # interpola os buracos
    conhecidos = [i for i, o in enumerate(out) if o["s"] is not None]
    for i, o in enumerate(out):
        if o["s"] is not None:
            continue
        antes = max((k for k in conhecidos if k < i), default=None)
        depois = min((k for k in conhecidos if k > i), default=None)
        t0 = out[antes]["e"] if antes is not None else 0.0
        t1 = out[depois]["s"] if depois is not None else dur
        faltam = (depois if depois is not None else len(out)) - (antes if antes is not None else -1) - 1
        pos = i - (antes if antes is not None else -1)
        passo = max(0.05, (t1 - t0) / max(1, faltam))
        o["s"], o["e"] = t0 + passo * (pos - 1), t0 + passo * pos
    for o in out:
        o["s"], o["e"] = max(0, min(o["s"], dur - 0.05)), max(0, min(o["e"], dur))
    return out


def quieto(jan, lim, i0, passo, minimo):
    """A partir de i0, andando no sentido 'passo', acha o primeiro trecho quieto de 'minimo' janelas."""
    q, i = 0, i0
    while 0 <= i < len(jan):
        q = q + 1 if jan[i][1] < lim else 0
        if q >= minimo:
            return i
        i += passo
    return None


def achar_frase(palavras, frase, perto=None, depois_de=0):
    """Índices (primeira, última) da frase na transcrição. 'perto' = segundo aproximado
    pra desempatar quando a frase aparece mais de uma vez."""
    alvo = [norm(x) for x in frase.split() if norm(x)]
    ws = [norm(p["w"]) for p in palavras]
    achados = [i for i in range(depois_de, len(ws) - len(alvo) + 1) if ws[i:i + len(alvo)] == alvo]
    if not achados:
        sys.exit(f"Frase não encontrada na transcrição: {frase!r}")
    if perto is not None:
        achados.sort(key=lambda i: abs(palavras[i]["s"] - perto))
    return achados[0], achados[0] + len(alvo) - 1


def ajustar_corte(fonte, palavras, t, lado, idx=None):
    """Leva o ponto de corte pro silêncio real entre palavras, sem comer sílaba nem
    pegar pedaço da palavra vizinha. Confirma o tempo da palavra com transcrição local."""
    if idx is not None:
        pass
    elif lado == "ini":
        idx = next((i for i, p in enumerate(palavras) if p["s"] >= t - 0.15), None)
    else:
        idx = max((i for i, p in enumerate(palavras) if p["s"] < t - 0.05), default=None)
    if idx is None:
        return t
    g = palavras[idx]
    loc = palavras_locais(fonte, g["s"] - 4, g["s"] + 3)
    k = achar_local(palavras if lado == "fim" else palavras, loc, idx if lado == "fim" else idx + 2, g["s"]) \
        if loc else None
    if lado == "ini" and k is not None:
        k = max(0, k - 2) if norm(loc[k]["w"]) != norm(g["w"]) else k
        # garante que é a primeira palavra do trecho
        for j in range(max(0, k - 3), min(len(loc), k + 3)):
            if norm(loc[j]["w"]) == norm(g["w"]) and abs(loc[j]["s"] - g["s"]) < 1.0:
                k = j
                break
    w = loc[k] if k is not None else g
    jan = suavizar(energia(fonte, w["s"] - 0.8, w["e"] + 0.8))
    if not jan:
        return t
    fala = sorted(v for _, v in jan)
    lim = fala[int(len(fala) * 0.9)] * 0.10
    if lado == "fim":
        i0 = next((i for i, (tt, _) in enumerate(jan) if tt >= w["e"] - 0.03), len(jan) - 1)
        prox = loc[k + 1]["e"] if k is not None and k + 1 < len(loc) else w["e"] + 0.5
        i = quieto(jan, lim, i0, 1, 10)  # 100 ms de silêncio de verdade
        if i is not None and jan[i][0] <= prox:
            return jan[i - 9][0] + 0.05
        cand = [x for x in jan if w["e"] - 0.03 <= x[0] <= min(prox - 0.05, w["e"] + 0.3)]
        return (min(cand, key=lambda x: x[1])[0] if cand else w["e"]) + 0.02
    i0 = max((i for i, (tt, _) in enumerate(jan) if tt <= w["s"] + 0.03), default=0)
    ant = loc[k - 1]["e"] - 0.03 if k is not None and k > 0 else w["s"] - 0.6
    i = quieto(jan, lim, i0, -1, 10)
    if i is not None and jan[i][0] >= ant:
        return jan[i + 9][0] - 0.04
    cand = [x for x in jan if max(ant + 0.05, w["s"] - 0.3) <= x[0] <= w["s"] + 0.03]
    return (min(cand, key=lambda x: x[1])[0] if cand else w["s"]) - 0.02


# ---------- vídeo ----------

HDR_SDR = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
           "zscale=t=bt709:m=bt709:r=tv,format=yuv420p,")


def e_hdr(fonte):
    """Vídeo HDR do iPhone (HLG/PQ): sem conversão a cor sai lavada, quase preto e branco."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", fonte], capture_output=True, text=True)
    return any(k in r.stderr for k in ("arib-std-b67", "smpte2084"))


# "cor" no plano: correção pra vídeo lavado (parede branca, luz fria de celular)
COR = {"viva": "eq=contrast=1.12:saturation=1.22:brightness=-0.025:gamma=0.96,"
               "colorbalance=rs=0.03:bs=-0.03:rm=0.025:bm=-0.025,",
       # "um pouco mais de cor" (aprovado pelo usuário em 29/10): leve, um pouco mais quente e saturado.
       # Não usar o grade escuro do Enrico inteiro.
       "henrico": "eq=contrast=1.06:brightness=-0.02:saturation=1.15:gamma=0.96,"
                  "colorbalance=rs=0.02:bs=-0.03:rm=0.03:bm=-0.04:rh=0.03:bh=-0.05,"}


def e_vertical(fonte):
    """Vídeo em pé (celular): largura < altura depois de aplicar a rotação."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", fonte], capture_output=True, text=True).stderr
    m = re.search(r"Video:.*?(\d{3,5})x(\d{3,5})", r)
    if not m:
        return False
    w, h = int(m[1]), int(m[2])
    if re.search(r"rotation of -?90", r):
        w, h = h, w
    return w < h


def filtro_layout(st, z, cx, tem_imagem, idx_img, hdr=False, cy=0.5, cor="", vertical=False):
    x = f"max(0\\,min(iw-ow\\,{cx}*iw-ow/2))"
    y = f"max(0\\,min(ih-oh\\,{cy}*ih-oh/2))"
    vx, vy, vw, vh = st["video"]
    asp = vw / vh
    if vertical:
        # vídeo em pé: usa a largura inteira (sem zoom) e corta só a altura, no meio
        v = (f"[0:v]{HDR_SDR if hdr else ''}{COR.get(cor, '')}"
             f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1")
        cam = f"{v},crop=iw/{z}:iw/{asp:.4f}/{z}:{x}:{y},scale={vw}:{vh},setsar=1"
    else:
        v = (f"[0:v]{HDR_SDR if hdr else ''}{COR.get(cor, '')}"
             f"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080:(iw-ow)/2:{y},setsar=1")
        cam = f"{v},crop=ih*{asp:.4f}/{z}:ih/{z}:{x}:(ih-oh)/2,scale={vw}:{vh},setsar=1"
    if st.get("raio"):
        # cantos arredondados: máscara preta calculada uma vez (loop) e posta por cima do vídeo
        r = st["raio"]
        m = f"lte(pow(max(0,max({r}-X,X-(W-1-{r}))),2)+pow(max(0,max({r}-Y,Y-(H-1-{r}))),2),{r * r})"
        cam += (f"[c0];color=black:s={vw}x{vh}:r={FPS}:d=1,format=rgba,"
                f"geq=r=0:g=0:b=0:a='255*(1-{m})',loop=loop=-1:size=1[mk];"
                f"[c0][mk]overlay=shortest=1,format=yuv420p")
    if "baixo" not in st:
        return f"{cam},pad={W}:{H}:{vx}:{vy}:black[v]"
    bx, by, bw, bh = st["baixo"]
    if tem_imagem:
        baixo = (f"[{idx_img}:v]scale={bw}:{bh}:force_original_aspect_ratio=increase,"
                 f"crop={bw}:{bh},setsar=1[d]")
        return f"{cam}[t];{baixo};[t][d]vstack[v]"
    return (f"{v},split[a][b];[a]crop=ih*{asp:.4f}/{z}:ih/{z}:{x}:(ih-oh)/2,scale={vw}:{vh},setsar=1[t];"
            f"[b]crop=ih*{bw / bh:.4f}:ih:(iw-ow)/2:0,scale={bw}:{bh},setsar=1[d];[t][d]vstack[v]")


# ---------- legendas e título ----------

def ass_tempo(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def cabecalho(st):
    t, l = st["titulo"], st["leg"]
    fmt = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
           "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
           "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
    estilos = [
        f"Style: Titulo,{t['fonte']},{t['tam']},{t['cor']},{t['cor']},{PRETO},&H64000000,0,0,0,0,100,100,0,0,"
        f"1,{t['contorno']},{t['sombra']},2,40,40,0,1",
        f"Style: Leg,{l['fonte']},{l['tam']},{l['cor']},{l['cor']},{PRETO},&H80000000,{-1 if l.get('negrito') else 0},0,0,0,"
        f"100,100,0,0,1,{l['contorno']},{l['sombra']},5,40,40,0,1",
        f"Style: Rotulo,CV Montserrat ExtraBold,62,{PRETO},{PRETO},{AMARELO},{AMARELO},-1,0,0,0,100,100,2,0,3,14,0,5,0,0,0,1",
        f"Style: Handle,CV Poppins SemiBold Italic,79,{BRANCO},{BRANCO},{PRETO},&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1",
    ]
    return ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2",
            "ScaledBorderAndShadow: yes", "", "[V4+ Styles]", fmt] + estilos + [
            "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]


def linhas_titulo(st, plano):
    tx = plano.get("titulo", "")
    if "caixa_vermelha" in st["titulo"]:
        tx = tx.upper()
    if st["destaque"]:
        tx = re.sub(r"\*(.+?)\*", lambda m: f"{{\\c{AMARELO}&}}{m[1]}{{\\c{BRANCO}&}}", tx)
    else:
        tx = tx.replace("*", "")
    return tx.split("\n")


def evento_titulo(st, plano, fim, so_ultima=False, dx=0):
    """Uma linha de ASS por linha do título, cada uma na altura medida na referência."""
    ys = list(st["titulo"]["linhas_y"])
    linhas = linhas_titulo(st, plano)
    passo = ys[1] - ys[0]
    if len(linhas) == 1:
        ys = [(ys[0] + ys[1]) // 2]
    while len(ys) < len(linhas):  # 3 linhas: sobe a primeira
        ys.insert(0, ys[0] - passo)
    ys = ys[-len(linhas):]
    out = []
    for k, (tx, y) in enumerate(zip(linhas, ys)):
        if so_ultima and k < len(linhas) - 1:
            continue
        out.append(f"Dialogue: 1,0:00:00.00,{fim},Titulo,,0,0,0,,{{\\an5\\pos({W // 2 + dx},{y})}}{tx}")
    return "\n".join(out)


def bbox_texto(st, plano, tmp, so_ultima):
    ass = os.path.join(tmp, "medir.ass")
    with open(ass, "w", encoding="utf-8") as f:
        f.write("\n".join(cabecalho(st) + [evento_titulo(st, plano, "0:00:01.00", so_ultima)]) + "\n")
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"color=black:s={W}x{H}:d=0.1",
                        "-vf", f"ass=medir.ass:fontsdir={FONTES}", "-frames:v", "1", "-pix_fmt", "gray",
                        "-f", "rawvideo", "-"], cwd=tmp, capture_output=True)
    px = r.stdout
    x0, x1, ys = W, 0, []
    for y in range(H):
        linha = px[y * W:(y + 1) * W]
        if max(linha) > 100:
            ys.append(y)
            idx = [i for i, v in enumerate(linha) if v > 100]
            x0, x1 = min(x0, idx[0]), max(x1, idx[-1])
    return x0, ys[0], x1, ys[-1]


def eventos_henrico(st, plano, palavras):
    """Legenda do modelo enrico.delafiori (3 referências analisadas quadro a quadro).
    Gancho: bloco que se monta palavra a palavra (corte seco), linhas coladas em zigue-zague,
    palavras de ligação em itálico sublinhado menor, a última palavra grande embaixo que vira
    amarela e depois serifa itálica. O 2º bloco vai pro outro lado do rosto.
    Resto: alterna 'uma palavra grande por vez' no peito e 'frase pequena' do lado da cabeça
    (palavra entra cinza e fica branca); números em fonte condensada."""
    vx, vy, vw, vh = st["video"]
    l = st["leg"]
    g_ate = plano.get("_gancho", 0)
    rx = vx + int(vw * plano.get("rosto_x", 0.5))  # centro do rosto na tela
    limpa = lambda w: re.sub(r"[.,;:!?…\"]+$", "", w).lower()
    fim_frase = lambda p: p["w"][-1] in ".?!,"
    ligacao = set("o a os as e de do da que pra pro para te se um uma no na em com por ao".split())
    fraca = ligacao | set("eu me você voce é isso esse essa meu minha seu sua mais muito já não "
                          "tá aqui lá então cara tipo vai vou foi ser ter tem".split())
    sombra = "\\3c&H000000&\\3a&H98&\\bord5\\blur8\\shad0"
    num = lambda w: re.search(r"\d", w)
    fs_g, fs_p, fs_m = l["tam_gancho"], l["tam_palavra"], l["tam"]
    out = []
    ev = lambda a, b, tx: out.append(f"Dialogue: 1,{ass_tempo(a)},{ass_tempo(b)},Leg,,0,0,0,,{tx}")

    # ---------- frases (quebra em pontuação ou pausa) ----------
    frases, f = [], []
    for i, p in enumerate(palavras):
        f.append(p)
        prox = palavras[i + 1] if i + 1 < len(palavras) else None
        longa = len(f) >= 9 and limpa(p["w"]) not in fraca or len(f) >= 12
        if prox is None or fim_frase(p) or prox["s"] - p["e"] > 0.3 or longa:
            frases.append(f); f = []

    # ---------- gancho: blocos empilhados ----------
    blocos = []
    for fr in [fr for fr in frases if fr[0]["s"] < g_ate]:
        # blocos de até 5 palavras; sobra de 1-2 palavras fica no bloco anterior
        k = 0
        while k < len(fr):
            n = len(fr) - k if len(fr) - k <= 7 else 5
            # o bloco termina em palavra forte (ela vira o destaque grande)
            while n > 3 and k + n < len(fr) and limpa(fr[k + n - 1]["w"]) in fraca:
                n -= 1
            blocos.append(fr[k:k + n]); k += n
    resto = [p for p in palavras if p["s"] >= (blocos[-1][-1]["e"] if blocos else 0)]
    for bi, fr in enumerate(blocos):
        prox = blocos[bi + 1][0]["s"] if bi + 1 < len(blocos) else (resto[0]["s"] if resto else fr[-1]["e"] + 0.4)
        fim_b = min(prox, fr[-1]["e"] + 0.6)
        # linhas: palavra curta (<=3 letras) cola na próxima
        linhas, lin = [], []
        for p in fr[:-1]:
            lin.append(p)
            if len(limpa(p["w"])) > 3 or len(lin) == 2:
                linhas.append(lin); lin = []
        if lin:
            linhas.append(lin)
        ult = fr[-1]
        # lado: 1º bloco à esquerda do rosto, 2º à direita, alternando
        # cabe do lado direito do rosto? (vídeo com a pessoa no meio: não cabe)
        cabe_dir = (vx + vw) - (rx + int(vw * 0.10)) > vw * 0.40
        esq = bi % 2 == 0 or not cabe_dir
        x0 = vx + 40 if esq else rx + int(vw * 0.10)
        y = vy + 22
        zig = [0, 40, 0, 22, 8]
        for k, lin in enumerate(linhas):
            ws = [limpa(p["w"]) for p in lin]
            liga = all(w in ligacao for w in ws)
            fs = int(fs_g * (0.62 if liga else 1.0))
            est = "\\i1\\u1" if liga else ""
            x = x0 + zig[k % len(zig)]
            for j, p in enumerate(lin):
                b = fim_b
                tx = " ".join(w if m <= j else f"{{\\alpha&HFF&}}{w}{{\\alpha&H00&}}" for m, w in enumerate(ws))
                a = p["s"]
                b = lin[j + 1]["s"] if j + 1 < len(lin) else fim_b
                ev(a, b, f"{{\\an7\\pos({x},{y})\\fs{fs}\\fsp-3{est}{sombra}}}{tx}")
            y += int(fs * 0.80)
        # última palavra: grande embaixo, branca -> amarela -> serifa itálica amarela
        w = limpa(ult["w"])
        fsu = int(fs_g * 1.25)
        yb = max(y + int(fsu * 0.15), vy + int(vh * 0.55))
        xb = x0 + 10
        t1, t2 = ult["s"] + 0.30, ult["s"] + 0.55
        if num(w):
            ev(ult["s"], fim_b, f"{{\\an7\\pos({xb},{yb - 30})\\fnDIN Condensed\\b1\\fs{int(fsu * 1.5)}{sombra}}}{w.upper()}")
        else:
            ev(ult["s"], min(t1, fim_b), f"{{\\an7\\pos({xb},{yb})\\fs{fsu}\\fsp-3{sombra}}}{w}")
            if t1 < fim_b:
                ev(t1, min(t2, fim_b), f"{{\\an7\\pos({xb},{yb})\\fs{fsu}\\fsp-3\\c{AMARELO}&{sombra}}}{w}")
            if t2 < fim_b:
                ev(t2, fim_b, f"{{\\an7\\pos({xb},{yb - 6})\\fnDidot\\i1\\b0\\fs{int(fsu * 1.1)}\\fsp1"
                              f"\\c{AMARELO}&{sombra}}}{w}")

    # ---------- resto: alterna palavra grande / frase pequena ----------
    corpo = [fr for fr in frases if fr[0]["s"] >= g_ate]
    lado = 0
    for fi, fr in enumerate(corpo):
        fim_f = corpo[fi + 1][0]["s"] if fi + 1 < len(corpo) else fr[-1]["e"] + 0.3
        fim_f = min(fim_f, fr[-1]["e"] + 0.35)
        modo_grande = len(fr) <= 4 or fi % 2 == 0
        if modo_grande:
            # uma palavra por vez, grande, no peito, troca seca
            for j, p in enumerate(fr):
                w = limpa(p["w"])
                b = fr[j + 1]["s"] if j + 1 < len(fr) else fim_f
                if num(w):
                    tx = f"{{\\an2\\pos({rx},{vy + vh - 18})\\fnDIN Condensed\\b1\\fs{int(fs_p * 1.5)}{sombra}}}{w.upper()}"
                else:
                    fs = fs_p if len(w) <= 8 else int(fs_p * 0.85)
                    tx = f"{{\\an2\\pos({rx},{vy + vh - 30})\\fs{fs}\\fsp-2{sombra}}}{w}"
                ev(p["s"], b, tx)
        else:
            # frase pequena do lado da cabeça, em pedaços de até 4 palavras (2 por linha)
            pedacos = [fr[k:k + 4] for k in range(0, len(fr), 4)]
            for pi, pd in enumerate(pedacos):
                ws = [limpa(p["w"]) for p in pd]
                amarelo = any(num(w) or re.search(r"^mil|milh|rolex|reais|d[oó]lares", w) for w in ws) \
                    or (pi == len(pedacos) - 1 and fi % 4 == 1)
                cor = AMARELO if amarelo else BRANCO
                esq = lado % 2 == 0
                lado += 1
                px = vx + int(vw * 0.22) if esq else rx + int(vw * 0.27)
                py = vy + int(vh * 0.20)
                fim_p = pedacos[pi + 1][0]["s"] if pi + 1 < len(pedacos) else fim_f
                for j, p in enumerate(pd):
                    b = pd[j + 1]["s"] if j + 1 < len(pd) else fim_p
                    partes = []
                    for m, w in enumerate(ws):
                        if m > j:
                            a_tag = "\\1a&HFF&\\3a&HFF&"
                        elif m == j:
                            a_tag = "\\1c&HB0B0B0&\\t(0,120,\\1c" + cor + "&)"
                        else:
                            a_tag = ""
                        quebra = "\\N" if m == 1 and len(ws) > 2 else " "
                        partes.append(f"{{\\1c{cor}&\\1a&H00&\\3a&H98&{a_tag}}}{w}{quebra if m < len(ws) - 1 else ''}")
                    ev(p["s"], b, f"{{\\an8\\pos({px},{py})\\fs{fs_m}\\fsp-1\\q2{sombra}}}" + "".join(partes))
    return out


def eventos_rotulo(st, plano):
    """Rótulo por segmento ("CONSELHO 1"...): caixa amarela que entra com um pop.
    Henrico: acima da caixa do vídeo; os outros: no alto do vídeo."""
    out = []
    vx, vy, vw, vh = st["video"]
    y = vy - 75 if st["leg"].get("modo") == "henrico" else vy + 80
    for a, b, tx in plano.get("_rotulos", []):
        out.append(f"Dialogue: 2,{ass_tempo(a)},{ass_tempo(b)},Rotulo,,0,0,0,,"
                   f"{{\\an5\\pos({vx + vw // 2},{y})\\fscx70\\fscy70\\t(0,120,\\fscx108\\fscy108)"
                   f"\\t(120,200,\\fscx100\\fscy100)}}{tx}")
    return out


def montar_ass(st, plano, palavras, dur, dx=0):
    linhas = cabecalho(st) + eventos_rotulo(st, plano)
    fim = ass_tempo(dur)
    if plano.get("titulo"):
        linhas.append(evento_titulo(st, plano, fim, dx=dx))
    if st["handle"]:
        linhas.append(f"Dialogue: 1,0:00:00.00,{fim},Handle,,0,0,0,,{{\\pos({W // 2},{st['handle_y']})}}{HANDLE}")
    l = st["leg"]
    if plano.get("sem_legenda"):
        # henrico_pro.py desenha as legendas depois (atrás da pessoa, fotos, animação)
        return "\n".join(linhas) + "\n"
    if l.get("modo") == "henrico":
        return "\n".join(linhas + eventos_henrico(st, plano, palavras)) + "\n"
    n = l["palavras"]
    # agrupa até n palavras, quebrando em pausa > 0.35s ou pontuação
    grupos, g = [], []
    for i, p in enumerate(palavras):
        g.append(p)
        prox = palavras[i + 1] if i + 1 < len(palavras) else None
        if len(g) >= n or prox is None or prox["s"] - p["e"] > 0.35 or p["w"][-1] in ".?!,":
            grupos.append(g); g = []
    efeito = "{\\blur%s}" % l["blur"] if l.get("blur") else ""
    if l.get("brilho"):
        efeito = "{\\3c&H000000&\\bord6\\blur8}"
    for i, g in enumerate(grupos):
        ini, fim_g = g[0]["s"], g[-1]["e"]
        if i + 1 < len(grupos) and grupos[i + 1][0]["s"] - fim_g < 0.6:
            fim_g = grupos[i + 1][0]["s"]
        tx = " ".join(re.sub(r"[.,;:!…\"]+$", "", p["w"]) for p in g)
        tx = tx.upper() if l["caixa"] == "mai" else tx.lower()
        camada = ""
        if l.get("brilho"):
            # brilho escuro por baixo + texto limpo por cima, como no jon
            linhas.append(f"Dialogue: 0,{ass_tempo(ini)},{ass_tempo(fim_g)},Leg,,0,0,0,,"
                          f"{{\\pos({W // 2},{l['y']})}}{efeito}{tx}")
            camada = "{\\bord0}"
        linhas.append(f"Dialogue: 1,{ass_tempo(ini)},{ass_tempo(fim_g)},Leg,,0,0,0,,"
                      f"{{\\pos({W // 2},{l['y']})}}{camada}{'' if l.get('brilho') else efeito}{tx}")
    return "\n".join(linhas) + "\n"


def achar_musica(nome):
    if not nome:
        return None
    for f in sorted(os.listdir(MUSICAS)):
        if nome.lower() in f.lower():
            return os.path.join(MUSICAS, f)
    sys.exit(f"Música não encontrada: {nome}")


def clipe_mitada(st, parte, saida, tmp):
    quadro = os.path.join(tmp, "ultimo.png")
    run(["ffmpeg", "-y", "-sseof", "-0.07", "-i", parte, "-frames:v", "1", "-update", "1", quadro])
    tam = 92 if st["emoji_mitada"] == "caveira" else 120
    ly = st["leg"]["y"]
    pb = "hue=s=0," if st["mitada_pb"] else ""
    run(["ffmpeg", "-y", "-loop", "1", "-i", quadro, "-i", os.path.join(EMOJI, st["emoji_mitada"] + ".png"),
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
         "-filter_complex", f"[0:v]{pb}setsar=1[bw];[1:v]scale={tam}:{tam}:flags=lanczos[e];"
                            f"[bw][e]overlay={W // 2 - tam // 2}:{ly - tam // 2},format=yuv420p[v]",
         "-map", "[v]", "-map", "2:a", "-t", str(st["dur_mitada"]), "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", saida])


def clipe_cauda(parte, dur, saida, tmp):
    quadro = os.path.join(tmp, "cauda.png")
    run(["ffmpeg", "-y", "-sseof", "-0.07", "-i", parte, "-frames:v", "1", "-update", "1", quadro])
    run(["ffmpeg", "-y", "-loop", "1", "-i", quadro, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
         "-vf", "format=yuv420p", "-t", str(dur), "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "17", "-c:a", "aac", "-b:a", "192k", saida])


def main():
    global IDIOMA
    with open(sys.argv[1], encoding="utf-8") as f:
        plano = json.load(f)
    IDIOMA = plano.get("idioma", "pt")
    nome_est = ALIAS.get(plano["estilo"], plano["estilo"])
    st = json.loads(json.dumps(E[nome_est]))
    if st.get("sem_titulo"):
        plano = {**plano, "titulo": ""}
    if plano.get("titulo") and not plano.get("titulo_fixo"):
        # título largo demais: diminui a fonte até caber (com folga pro emoji)
        tmp0 = tempfile.mkdtemp()
        for _ in range(4):
            x0, _, x1, _ = bbox_texto(st, plano, tmp0, False)
            if x1 - x0 <= 960:
                break
            st["titulo"]["tam"] = int(st["titulo"]["tam"] * 960 / (x1 - x0))
        shutil.rmtree(tmp0)
    img = plano.get("imagem_inferior") if "baixo" in st else None
    tmp = tempfile.mkdtemp(prefix="corte_")
    partes, palavras, t = [], [], 0.0
    mitadas = []  # (inicio, fim) na linha do tempo final
    juntas = []  # fim de cada segmento na linha do tempo final
    cache, hdrs = {}, {}
    segs = plano["segmentos"]

    for i, seg in enumerate(segs):
        fonte = seg["fonte"]
        if fonte not in cache:
            pj = os.path.join(fonte + ".cortes", "palavras.json")
            if not os.path.exists(pj):
                sys.exit(f"Rode antes: transcrever.py {fonte}")
            with open(pj, encoding="utf-8") as f:
                cache[fonte] = json.load(f)
        pal = cache[fonte]
        if "de" in seg:
            perto = seg.get("perto")
            i0, _ = achar_frase(pal, seg["de"], perto)
            _, i1 = achar_frase(pal, seg["ate"], pal[i0]["s"] + 0.5 if perto is None else perto, depois_de=i0)
            if i1 < i0:
                sys.exit(f"'ate' vem antes de 'de' no segmento {i}")
            ini = (float(seg["inicio_exato"]) if "inicio_exato" in seg
                   else ajustar_corte(fonte, pal, pal[i0]["s"], "ini", idx=i0))
            fim = (float(seg["fim_exato"]) if "fim_exato" in seg
                   else ajustar_corte(fonte, pal, pal[i1]["e"], "fim", idx=i1))
        else:
            ini = (float(seg["inicio_exato"]) if "inicio_exato" in seg
                   else ajustar_corte(fonte, pal, float(seg["inicio"]), "ini"))
            fim = (float(seg["fim_exato"]) if "fim_exato" in seg
                   else ajustar_corte(fonte, pal, float(seg["fim"]), "fim"))
        d = fim - ini
        z = float(seg.get("zoom", 1.0))
        cx = float(seg.get("crop_x", plano.get("crop_x", 0.5)))
        saida = os.path.join(tmp, f"p{i:03d}.mp4")
        cmd = ["ffmpeg", "-y"]
        cob = seg.get("cobertura")
        if cob:
            cmd += (["-loop", "1", "-i", cob] if cob.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
                    else ["-stream_loop", "-1", "-i", cob])
            z, cx = 1.0, 0.5
        else:
            cmd += ["-ss", f"{ini:.3f}", "-to", f"{fim:.3f}", "-i", fonte]
        cmd += ["-ss", f"{ini:.3f}", "-to", f"{fim:.3f}", "-i", fonte]
        idx_img = 2
        if img:
            cmd += ["-loop", "1", "-i", img]
        # fotos por cima do vídeo por alguns segundos, no momento em que a fala cita o assunto
        if fonte not in hdrs:
            hdrs[fonte] = (e_hdr(fonte), e_vertical(fonte))
        cy = float(seg.get("crop_y", plano.get("crop_y", 0.5)))
        fv = filtro_layout(st, z, cx, bool(img), idx_img, hdrs[fonte][0] and not cob,
                           0.5 if cob else cy, "" if cob else plano.get("cor", ""),
                           hdrs[fonte][1] and not cob)
        n_in = 3 if img else 2
        vx, vy, vw, vh = st["video"]
        ult = "v"
        for k, ft in enumerate(seg.get("fotos", [])):
            arq = ft["arquivo"] if os.path.isabs(ft["arquivo"]) else os.path.join(FOTOS, ft["arquivo"])
            if "em" in ft and "de" in seg:
                kk, _ = achar_frase(pal, ft["em"], pal[i0]["s"], depois_de=i0)
                a = max(0.0, pal[kk]["s"] - ini)
            else:
                a = float(ft.get("aos", 0))
            dur_f = float(ft.get("dur", 1.6))
            cmd += ["-loop", "1", "-t", f"{d:.3f}", "-i", arq]
            fv = fv.replace(f"[{ult}]", f"[{ult}0]", 1) if k == 0 else fv
            src = f"{ult}0" if k == 0 else f"f{k - 1}"
            fv += (f";[{n_in}:v]scale={vw}:{vh}:force_original_aspect_ratio=increase,crop={vw}:{vh},setsar=1[fi{k}];"
                   f"[{src}][fi{k}]overlay={vx}:{vy}:enable='between(t\\,{a:.2f}\\,{a + dur_f:.2f})'[f{k}]")
            n_in += 1
        if seg.get("fotos"):
            fv += f";[f{len(seg['fotos']) - 1}]null[v]"
        cmd += ["-filter_complex", fv +
                f";[1:a]aresample=48000,aformat=channel_layouts=stereo,"
                f"afade=t=in:d=0.02,afade=t=out:st={max(0, d - 0.03):.3f}:d=0.03[a]",
                "-map", "[v]", "-map", "[a]", "-t", f"{d:.3f}", "-r", str(FPS),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", saida]
        run(cmd)
        partes.append(saida)
        # legenda: texto da transcrição completa (acerta mais as palavras) com o tempo
        # da transcrição do trecho já cortado (acerta mais o tempo)
        dseg = duracao(saida)
        if "de" not in seg:
            i0 = next((k for k, p in enumerate(pal) if p["s"] >= ini - 0.1), len(pal))
            i1 = max((k for k, p in enumerate(pal) if p["s"] < fim - 0.05), default=i0 - 1)
        for p in alinhar(pal[i0:i1 + 1], palavras_locais(saida, 0, dseg), dseg):
            palavras.append({"w": p["w"], "s": p["s"] + t, "e": p["e"] + t})
        if seg.get("rotulo"):
            rs = plano.setdefault("_rotulos", [])
            if rs and rs[-1][2] == seg["rotulo"] and abs(rs[-1][1] - t) < 0.01:
                rs[-1][1] = t + dseg  # mesmo rótulo no segmento seguinte: continua
            else:
                rs.append([t, t + dseg, seg["rotulo"]])
        t += dseg
        juntas.append(round(t, 3))

        if seg.get("mitada") or seg.get("caveira"):
            cl = os.path.join(tmp, f"p{i:03d}m.mp4")
            clipe_mitada(st, saida, cl, tmp)
            partes.append(cl)
            dm = duracao(cl)
            mitadas.append((t, t + dm))
            t += dm

    if st["cauda"] and not mitadas or (st["cauda"] and mitadas[-1][1] < t - 0.01):
        cl = os.path.join(tmp, "cauda.mp4")
        clipe_cauda(partes[-1], st["cauda"], cl, tmp)
        partes.append(cl)
        t += duracao(cl)

    lista = os.path.join(tmp, "lista.txt")
    with open(lista, "w") as f:
        f.writelines(f"file '{p}'\n" for p in partes)
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", os.path.join(tmp, "junto.mp4")])
    # henrico: o gancho (palavras grandes) vale no primeiro segmento, até 6s
    plano["_gancho"] = min(juntas[0], 5.0) if juntas else 0
    with open(os.path.join(tmp, "leg.ass"), "w", encoding="utf-8") as f:
        f.write(montar_ass(st, plano, palavras, t))

    # ----- composição final -----
    cmd = ["ffmpeg", "-y", "-i", "junto.mp4"]
    n_in = 1
    fv = "[0:v]"
    cadeia = []
    emojis = [e for e in plano.get("emoji_titulo", st["emoji_padrao"]).split(",") if e]
    if plano.get("titulo"):
        if "caixa_vermelha" in st["titulo"]:
            x0, y0, x1, y1 = bbox_texto(st, plano, tmp, False)
            lx0, ly0, lx1, ly1 = bbox_texto(st, plano, tmp, True)
            tam_e = int((ly1 - ly0) * 1.25)
            extra = (tam_e + 10) * len(emojis)
            fim_x = max(x1, lx1 + extra)
            # desloca o texto pra esquerda pra caixa ficar centrada com o emoji
            desl = (fim_x - x1) // 2 if fim_x > x1 else 0
            bx0, bx1 = x0 - 22 - desl, fim_x + 22 - desl
            cadeia.append(f"drawbox=x={bx0}:y={y0 - 20}:w={bx1 - bx0}:h={y1 - y0 + 40}:color=0xE10600@1:t=fill")
            ex, ey = lx1 + 12 - desl, (ly0 + ly1) // 2 - tam_e // 2
            with open(os.path.join(tmp, "leg.ass"), "w", encoding="utf-8") as f:
                f.write(montar_ass(st, plano, palavras, t, dx=-desl))
        else:
            lx0, ly0, lx1, ly1 = bbox_texto(st, plano, tmp, True)
            tam_e = int((ly1 - ly0) * 1.15)
            ex, ey = lx1 + 4, (ly0 + ly1) // 2 - tam_e // 2
    cadeia.append(f"ass=leg.ass:fontsdir={FONTES}")
    filtro = f"{fv}{','.join(cadeia)}[v0]"
    ult = "v0"
    if plano.get("titulo"):
        for k, e in enumerate(emojis):
            cmd += ["-i", os.path.join(EMOJI, e + ".png")]
            filtro += (f";[{n_in}:v]scale={tam_e}:{tam_e}:flags=lanczos[e{k}];"
                       f"[{ult}][e{k}]overlay={ex + k * (tam_e + 4)}:{ey}[v{k + 1}]")
            ult = f"v{k + 1}"
            n_in += 1
    filtro += f";[{ult}]null[v]"

    # áudio: voz normalizada + música por baixo (some durante as mitadas) + som da mitada
    filtro += f";[0:a]apad=pad_dur=4,loudnorm=I=-15:TP=-1.5:LRA=11,aresample=48000,atrim=0:{t:.3f}[voz]"
    mix = ["[voz]"]
    musica = achar_musica(plano.get("musica", ""))
    fim_musica = t
    if nome_est == "tino" and mitadas:
        fim_musica = mitadas[-1][0]
    if musica:
        cmd += ["-stream_loop", "-1", "-i", musica]
        corte = "+".join(f"between(t\\,{a:.2f}\\,{b:.2f})" for a, b in mitadas) or "0"
        vol_db = float(plano.get("volume_musica_db", -11))
        filtro += (f";[{n_in}:a]atrim=start={plano.get('musica_inicio', 0)},asetpts=PTS-STARTPTS,"
                   f"aresample=48000,aformat=channel_layouts=stereo,atrim=0:{fim_musica + 4:.3f},"
                   f"loudnorm=I=-14:TP=-1:LRA=7,aresample=48000,atrim=0:{fim_musica:.3f},volume={vol_db}dB,"
                   f"volume='if({corte}\\,0\\,1)':eval=frame,afade=t=in:d=0.3,"
                   f"afade=t=out:st={max(0, fim_musica - 0.25):.3f}:d=0.25,apad[mus]")
        mix.append("[mus]")
        n_in += 1
    for k, (a, b) in enumerate(mitadas):
        cmd += ["-i", SOM_MITADA]
        ms = int(a * 1000)
        filtro += (f";[{n_in}:a]atrim=0:{b - a:.3f},afade=t=out:st={max(0, b - a - 0.25):.3f}:d=0.25,"
                   f"volume=0.95,adelay={ms}|{ms},apad[s{k}]")
        mix.append(f"[s{k}]")
        n_in += 1
    filtro += f";{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0,alimiter=limit=0.95[a]"

    cmd += ["-filter_complex", filtro, "-map", "[v]", "-map", "[a]", "-t", f"{t:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "out.mp4"]
    run(cmd, cwd=tmp)
    os.makedirs(os.path.dirname(os.path.abspath(plano["saida"])), exist_ok=True)
    shutil.move(os.path.join(tmp, "out.mp4"), plano["saida"])
    # voz sem música, só pra revisão (revisar.py apaga depois)
    run(["ffmpeg", "-y", "-i", os.path.join(tmp, "junto.mp4"), "-vn", "-ac", "1", "-ar", "16000",
         os.path.splitext(plano["saida"])[0] + ".voz.wav"])
    with open(os.path.splitext(plano["saida"])[0] + ".texto.json", "w", encoding="utf-8") as f:
        json.dump({"palavras": palavras, "mitadas": mitadas, "juntas": juntas, "dur": t}, f, ensure_ascii=False)
    shutil.rmtree(tmp)
    print(f"Pronto: {plano['saida']} ({t:.1f}s, {len(mitadas)} mitadas)")


if __name__ == "__main__":
    main()
