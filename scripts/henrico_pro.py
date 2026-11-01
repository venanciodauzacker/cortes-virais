"""Henrico "pro": legenda com motion (Remotion), texto atrás da cabeça e das mãos, fotos entrando no vídeo.
Modelado nos 3 vídeos do enrico.delafiori (MODELOS DE CORTES/enrico*.mp4).

Uso: python3 -I henrico_pro.py <plano_pro.json>

Antes:
  1. renderizar.py com "estilo": "henrico" e "sem_legenda": true  -> base (com música) + .texto.json
  2. quadros da caixa: ffmpeg -i base.mp4 -vf crop=912:513:84:703 q/%05d.jpg
  3. scripts/mascara/mascara q m                                   -> pessoa inteira (Vision)
  Camadas: gancho, frases do lado e destaques passam ATRÁS do corpo inteiro (máscara m);
  as palavras grandes do peito ficam na frente de tudo. Nunca cortar no pescoço.
Plano:
{
  "base": ".../50-x_base.mp4", "mascaras": ".../m", "saida": ".../50-x_henrico-pro.mp4",
  "rosto_x": 0.55,
  "destaques": ["300", "80%"],            # palavras que ficam amarelas (número em fonte condensada)
  "riscar": ["cartão"],                   # no gancho: palavra riscada em amarelo
  "fotos": [{"de": 9.2, "ate": 10.4, "img": ".../foto.jpg"}]
}
"""
import json
import os
import re
import subprocess
import sys
import tempfile

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOTION = os.path.join(SKILL, "motion")
VX, VY, VW, VH = 84, 703, 912, 513      # caixa do modelo henrico (renderizar.py)
RAIO = 34
FPS = 30
LIGACAO = set("o a os as e de do da que pra pro para te se um uma no na em com por ao".split())
FRACA = LIGACAO | set("eu me você voce é isso esse essa meu minha seu sua mais muito já não "
                      "tá aqui lá então cara tipo vai vou foi ser ter tem né entendeu aí".split())


def limpa(w):
    w = re.sub(r"^[\"“(]+|[.,;:!?…\"”)]+$", "", w)
    # nome próprio (Érico, Rocha, Instagram) fica com maiúscula; o resto vai pra minúscula
    return w if re.match(r"^[A-ZÁÉÍÓÚÂÊÔÃÕ][a-záéíóúâêôãõç]{2,}$", w) and w.lower() not in FRACA else w.lower()


def fr(t):
    return int(round(t * FPS))


def frases_de(palavras, quebra_longa=True):
    frases, f = [], []
    for i, p in enumerate(palavras):
        f.append(p)
        prox = palavras[i + 1] if i + 1 < len(palavras) else None
        longa = quebra_longa and (len(f) >= 8 and limpa(p["w"]) not in FRACA or len(f) >= 11)
        if prox is None or p["w"][-1] in ".?!," or prox["s"] - p["e"] > 0.3 or longa:
            frases.append(f)
            f = []
    return frases


def montar(palavras, plano, dur):
    rx = int(VW * plano.get("rosto_x", 0.5))
    fotos = plano.get("fotos", [])
    em_foto = lambda t: any(f["de"] - 0.05 <= t < f["ate"] for f in fotos)
    destaques = [d.lower() for d in plano.get("destaques", [])]
    riscar = [d.lower() for d in plano.get("riscar", [])]
    # "6 em 7" marca o 6 e o 7, nunca o "em" solto no resto do vídeo
    eh_dest = lambda w: any(w.lower() == d or (w.lower() in d.split() and w.lower() not in FRACA) for d in destaques)
    num = lambda w: bool(re.search(r"\d", w))
    els = []
    juntas = plano["_juntas"]
    g_ate = plano.get("gancho", min(juntas[0], 5.0) if juntas else 3.0)

    # ---------- gancho: blocos empilhados e colados, à esquerda ----------
    gancho = frases_de([p for p in palavras if p["s"] < g_ate], False)
    blocos = []
    for f in gancho:
        while len(f) > 7:
            k = 6
            while k > 3 and limpa(f[k - 1]["w"]) in FRACA:
                k -= 1
            blocos.append(f[:k])
            f = f[k:]
        blocos.append(f)
    for bi, bl in enumerate(blocos):
        prox = blocos[bi + 1][0]["s"] if bi + 1 < len(blocos) else bl[-1]["e"] + 0.6
        fim = min(prox, bl[-1]["e"] + 0.7)
        corpo, ult = bl[:-1], bl[-1]
        fin_t = limpa(ult["w"])
        if corpo and limpa(corpo[-1]["w"])[:1].isupper():          # "Érico Rocha" vira o final junto
            fin_t = limpa(corpo[-1]["w"]) + " " + fin_t
            ult = corpo[-1]
            corpo = corpo[:-1]
        linhas, lin = [], []
        for j, p in enumerate(corpo):
            w = limpa(p["w"])
            st = "k" if w.lower() in riscar else "i" if j == 1 and len(corpo) > 2 else "s" if len(w) <= 2 else "n"
            lin.append({"t": w, "f": fr(p["s"]), "st": st})
            if len(w) > 3 or len(lin) == 2:
                linhas.append(lin)
                lin = []
        if lin:
            linhas.append(lin)
        els.append({"k": "hook", "cam": "atras", "a": fr(bl[0]["s"]), "b": fr(fim), "x": 26, "y": 16, "fs": 58,
                    "lines": linhas, "fin": {"t": fin_t, "f": fr(ult["s"]), "num": num(fin_t), "dx": 2}})

    # ---------- resto ----------
    corpo = [f for f in frases_de(palavras) if f[0]["s"] >= g_ate]
    lado = 0
    for fi, f in enumerate(corpo):
        fim_f = min(corpo[fi + 1][0]["s"] if fi + 1 < len(corpo) else dur, f[-1]["e"] + 0.35)
        ws = [limpa(p["w"]) for p in f]
        foto = any(em_foto(p["s"]) for p in f)
        tem_dest = any(eh_dest(w) for w in ws)
        if len(f) <= 5 or tem_dest or foto:
            # uma palavra por vez, grande, no peito (o texto passa por cima da camisa, atrás das mãos)
            for j, p in enumerate(f):
                w = ws[j]
                b = f[j + 1]["s"] if j + 1 < len(f) else fim_f
                meio = em_foto(p["s"])
                n = num(w)
                if eh_dest(w) and not meio:
                    # destaque: gigante, amarelo, em fonte condensada, encostado atrás da cabeça
                    fs = 190 if n else 150
                    larg = len(w) * fs * (0.40 if n else 0.38)
                    esq = rx - 55 - 16 >= larg or rx - 55 >= VW - rx - 55
                    if larg > (rx - 71 if esq else VW - rx - 71):
                        fs = int(fs * (rx - 71 if esq else VW - rx - 71) / larg)
                    els.append({"k": "big", "cam": "atras", "a": fr(p["s"]), "b": max(fr(b), fr(p["s"]) + 18),
                                "t": w, "x": rx - 55 if esq else rx + 55, "y": int(VH * 0.33), "fs": fs,
                                "al": "r" if esq else "l", "amarelo": True, "num": True, "meio": False})
                    continue
                fs = (118 if n else 84) if meio else (100 if n else 74 if len(w) <= 9 else 62)
                # o topo da palavra fica abaixo do queixo (a máscara da cabeça vai até o ombro)
                els.append({"k": "big", "cam": "frente", "a": fr(p["s"]), "b": max(fr(b), fr(p["s"]) + 3), "t": w,
                            "x": VW // 2 if meio else rx, "y": VH // 2 if meio else int(VH * 0.67 + fs * 0.5),
                            "fs": fs, "amarelo": eh_dest(w), "num": n, "meio": meio})
        else:
            # frase pequena do lado da cabeça: linhas de 2 palavras que se acumulam, cinza -> branco
            pedacos = [f[k:k + 6] for k in range(0, len(f), 6)]
            for pi, pd in enumerate(pedacos):
                esq = lado % 3 != 2          # quase sempre à esquerda (como ele), às vezes à direita
                lado += 1
                fim_p = pedacos[pi + 1][0]["s"] if pi + 1 < len(pedacos) else fim_f
                linhas = [[{"t": limpa(p["w"]), "f": fr(p["s"])} for p in pd[k:k + 2]] for k in range(0, len(pd), 2)]
                els.append({"k": "side", "cam": "atras", "a": fr(pd[0]["s"]), "b": fr(fim_p) + 4, "lado": "e" if esq else "d",
                            "x": rx - 72 if esq else rx + 72, "y": int(VH * 0.26), "fs": 30,
                            "lines": linhas, "amarelos": [limpa(p["w"]) for p in pd if eh_dest(limpa(p["w"]))]})
    return els


def main():
    plano = json.load(open(sys.argv[1], encoding="utf-8"))
    base = plano["base"]
    info = json.load(open(os.path.splitext(base)[0] + ".texto.json", encoding="utf-8"))
    palavras, dur = info["palavras"], info["dur"]
    plano["_juntas"] = info.get("juntas", [])
    # foto por palavra: {"palavra": "365", "img": ...} entra na 1ª vez que a palavra é dita, por ~1,2s
    for f in plano.get("fotos", []):
        if "palavra" in f and "de" not in f:
            alvo = f["palavra"].lower()
            p = next((p for p in palavras if limpa(p["w"]).lower() == alvo), None)
            if p:
                f["de"], f["ate"] = round(p["s"] - 0.05, 2), round(min(dur - 0.2, p["s"] + 1.25), 2)
    plano["fotos"] = [f for f in plano.get("fotos", []) if "de" in f]
    els = montar(palavras, plano, dur)
    tmp = tempfile.mkdtemp()
    props = os.path.join(tmp, "props.json")
    json.dump({"dur": dur, "els": els}, open(props, "w", encoding="utf-8"), ensure_ascii=False)
    movs = {}
    for cam in ("atras", "frente"):
        # atrás: passa por trás do corpo inteiro; frente: por cima de tudo
        json.dump({"dur": dur, "els": els, "camada": cam}, open(props, "w", encoding="utf-8"), ensure_ascii=False)
        movs[cam] = os.path.join(tmp, f"{cam}.mov")
        r = subprocess.run(["npx", "remotion", "render", "src/index.ts", "Legendas", movs[cam], f"--props={props}",
                            "--codec=prores", "--prores-profile=4444", "--pixel-format=yuva444p10le",
                            "--image-format=png", "--log=error"], cwd=MOTION)
        if r.returncode:
            sys.exit("Remotion falhou")

    fotos = plano.get("fotos", [])
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", base,
           "-framerate", str(FPS), "-i", os.path.join(plano["mascaras"], "%05d.png"),
           "-i", movs["atras"], "-i", movs["frente"]]
    for f in fotos:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{f['ate'] + 0.2:.2f}", "-i", f["img"]]
    r = RAIO
    canto = f"lte(pow(max(0,max({r}-X,X-(W-1-{r}))),2)+pow(max(0,max({r}-Y,Y-(H-1-{r}))),2),{r * r})"
    g = [f"[0:v]format=rgba,crop={VW}:{VH}:{VX}:{VY},split=2[c1][c2]"]
    ult = "c1"
    for k, f in enumerate(fotos):
        a, b = f["de"], f["ate"]
        # foto inteira por cima de um fundo borrado dela mesma (serve pra print em pé)
        g.append(f"[{k + 4}:v]setsar=1,split=2[fa{k}][fb{k}]")
        g.append(f"[fa{k}]scale={VW}:{VH}:force_original_aspect_ratio=increase,crop={VW}:{VH},"
                 f"boxblur=24:2,eq=brightness=-0.18[fz{k}]")
        g.append(f"[fb{k}]scale=-2:{VH}[fn{k}]")
        g.append(f"[fz{k}][fn{k}]overlay=(W-w)/2:0,format=rgba,"
                 f"fade=in:st={a:.2f}:d=0.10:alpha=1,fade=out:st={b - 0.10:.2f}:d=0.10:alpha=1[f{k}]")
        g.append(f"[{ult}][f{k}]overlay=enable='between(t,{a:.2f},{b:.2f})'[fo{k}]")
        ult = f"fo{k}"
    g.append(f"[{ult}][2:v]overlay=shortest=1[tx]")
    # a pessoa inteira por cima da camada de trás (menos durante as fotos)
    fora = "*".join(f"not(between(t,{f['de']:.2f},{f['ate']:.2f}))" for f in fotos) or "1"
    g.append(f"[1:v]scale={VW}:{VH},format=gray,boxblur=1:1[mk]")
    g.append("[c2][mk]alphamerge[pessoa]")
    g.append(f"[tx][pessoa]overlay=enable='{fora}'[cp]")
    g.append("[cp][3:v]overlay=shortest=1[cx]")
    g.append(f"color=black:s={VW}x{VH}:r={FPS}:d=1,format=rgba,geq=r=0:g=0:b=0:a='255*(1-{canto})',"
             "loop=loop=-1:size=1[mk2]")
    g.append("[cx][mk2]overlay=shortest=1[caixa]")
    g.append(f"[0:v][caixa]overlay={VX}:{VY},format=yuv420p[v]")
    if plano.get("teste"):
        cmd += ["-t", str(plano["teste"])]     # prévia curta pra conferir o visual
    cmd += ["-filter_complex", ";".join(g), "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium",
            "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", "-shortest",
            plano["saida"]]
    subprocess.run(cmd, check=True)
    print("Pronto:", plano["saida"], f"({dur:.1f}s, {len(els)} legendas, {len(fotos)} fotos)")


if __name__ == "__main__":
    main()
