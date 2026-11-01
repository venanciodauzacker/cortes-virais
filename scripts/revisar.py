#!/usr/bin/env python3
"""Revisa um corte pronto: palavras cortadas/faltando nas emendas, música e mitadas.

Uso: python3 revisar.py <corte.mp4> [idioma=pt]

Precisa do <corte>.texto.json que o renderizar.py grava. Gera também
<corte>.frames.jpg (um quadro a cada 2s) pra conferir enquadramento, título e legenda.
"""
import difflib, json, os, re, subprocess, sys, tempfile, unicodedata

MODELO = os.path.expanduser("~/tools/whisper-models/ggml-medium.bin")


def norm(w):
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9%]", "", w)


def rms_por_janela(video, passo=0.1):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", video, "-af",
                        f"asetnsamples={int(48000 * passo)},astats=metadata=1:reset=1,"
                        "ametadata=print:key=lavfi.astats.Overall.RMS_level", "-vn", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    ts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", r)]
    vs = [float(x) if x not in ("-inf", "inf") else -120 for x in re.findall(r"RMS_level=(-?[\w.]+)", r)]
    return list(zip(ts, vs))


def main():
    video = os.path.abspath(sys.argv[1])
    idioma = sys.argv[2] if len(sys.argv) > 2 else "pt"
    info = json.load(open(os.path.splitext(video)[0] + ".texto.json", encoding="utf-8"))
    esperado = info["palavras"]
    tmp = tempfile.mkdtemp()
    voz = os.path.splitext(video)[0] + ".voz.wav"
    wav = voz if os.path.exists(voz) else os.path.join(tmp, "a.wav")
    if wav != voz:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-i", video, "-ar", "16000", "-ac", "1", wav], check=True)
    subprocess.run(["whisper-cli", "-m", MODELO, "-l", idioma, "-f", wav, "-ml", "1", "-sow", "-oj",
                    "-of", os.path.join(tmp, "w")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    segs = json.load(open(os.path.join(tmp, "w.json"), encoding="utf-8", errors="replace"))["transcription"]
    ouvido = [{"w": s["text"].strip(), "s": s["offsets"]["from"] / 1000} for s in segs
              if s["text"].strip() and not s["text"].strip().startswith("[")]

    # emendas: ouve 4s em volta de cada uma, isolado, e mostra o que se escuta
    emendas = []
    for k, j in enumerate(info["juntas"][:-1]):
        trecho = os.path.join(tmp, f"j{k}.wav")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{max(0, j - 2):.2f}", "-t", "4", "-i", wav,
                        trecho], check=True)
        r = subprocess.run(["whisper-cli", "-m", MODELO, "-l", idioma, "-f", trecho, "-nt"],
                           capture_output=True, text=True, timeout=60)
        esp = " ".join(p["w"] for p in esperado if j - 2 <= p["s"] <= j + 2)
        emendas.append((j, esp, " ".join(r.stdout.split())))

    a = [norm(p["w"]) for p in esperado]
    b = [norm(p["w"]) for p in ouvido]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    problemas = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        t0 = esperado[i1]["s"] if i1 < len(esperado) else info["dur"]
        perto = min((abs(t0 - j) for j in info["juntas"]), default=99)
        problemas.append((t0, op, " ".join(p["w"] for p in esperado[i1:i2]),
                          " ".join(p["w"] for p in ouvido[j1:j2]), perto < 0.8))

    print(f"== {os.path.basename(video)}  {info['dur']:.1f}s  semelhança {sm.ratio():.0%}")
    graves = [p for p in problemas if p[4]]
    for t0, op, e, o, emenda in problemas:
        marca = "EMENDA" if emenda else "      "
        print(f"  {marca} {t0:6.1f}s {op:8s} esperado: {e!r:40s} ouvido: {o!r}")

    for j, esp, ouv in emendas:
        ok = difflib.SequenceMatcher(None, [norm(x) for x in esp.split()], [norm(x) for x in ouv.split()]).ratio()
        print(f"  emenda {j:5.1f}s [{ok:.0%}] esperado: {esp}")
        print(f"                   ouvido:   {ouv}")
        if ok < 0.7:
            graves.append(j)
    if os.path.exists(voz):
        os.remove(voz)

    # áudio
    rms = rms_por_janela(video)
    dur = info["dur"]
    mit = info["mitadas"]
    dentro = lambda t: any(x <= t <= y for x, y in mit)
    fala = sorted(v for t, v in rms if not dentro(t) and v > -90)
    piso = fala[int(len(fala) * 0.05)] if fala else -120
    mediana = fala[len(fala) // 2] if fala else -120
    print(f"  áudio: mediana {mediana:.1f} dB (ref ~-18)  piso {piso:.1f} dB (ref -30 a -37 = música por baixo)")
    for x, y in mit:
        v = [v for t, v in rms if x + 0.1 <= t <= x + 1.2]
        print(f"  mitada {x:.1f}s: {sum(v) / len(v):.1f} dB (ref ~-7)" if v else f"  mitada {x:.1f}s: sem áudio")
    ultimos = [v for t, v in rms if dur - 2.0 <= t <= dur - 0.3 and not dentro(t)]
    if ultimos and max(ultimos) < -45:
        print("  AVISO: fim sem som (música acabou antes do vídeo)")
    buracos, ini = [], None
    for t, v in rms:
        if v < -45 and not dentro(t) and t < dur - 0.4:
            ini = t if ini is None else ini
        else:
            if ini is not None and t - ini >= 0.5:
                buracos.append((ini, t))
            ini = None
    for x, y in buracos:
        print(f"  AVISO: silêncio de {y - x:.1f}s em {x:.1f}s")

    folha = os.path.splitext(video)[0] + ".frames.jpg"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", video, "-vf",
                    "fps=1/2,scale=216:384,tile=8x3", "-frames:v", "1", folha])
    print(f"  frames: {folha}")
    print(f"  RESULTADO: {'REVISAR' if graves or buracos or sm.ratio() < 0.85 else 'OK'}")


if __name__ == "__main__":
    main()
