#!/usr/bin/env python3
"""Transcreve um vídeo bruto com tempo por palavra.

Uso: python3 transcrever.py <video> [idioma=pt]

Gera, ao lado do vídeo, numa pasta <video>.cortes/:
  palavras.json   -> [{"w": "palavra", "s": 12.34, "e": 12.80}, ...]
  transcricao.txt -> frases com [mm:ss.s - mm:ss.s] pra escolher os momentos
Se já existir, não transcreve de novo.
"""
import json, os, subprocess, sys

MODELO = os.path.expanduser("~/tools/whisper-models/ggml-medium.bin")


def fmt(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def main():
    video = os.path.abspath(sys.argv[1])
    idioma = sys.argv[2] if len(sys.argv) > 2 else "pt"
    pasta = video + ".cortes"
    os.makedirs(pasta, exist_ok=True)
    pj = os.path.join(pasta, "palavras.json")
    if os.path.exists(pj):
        print(f"Já transcrito: {pasta}")
        return

    wav = os.path.join(pasta, "audio.wav")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", video,
                    "-ar", "16000", "-ac", "1", wav], check=True)
    base = os.path.join(pasta, "whisper")
    # -dtw dá o tempo de cada token alinhado ao áudio (o tempo normal erra até ~0,4s);
    # só funciona com flash attention desligada (-nfa)
    subprocess.run(["whisper-cli", "-m", MODELO, "-l", idioma, "-f", wav,
                    "-dtw", "medium", "-nfa", "-ojf", "-of", base],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    with open(base + ".json", encoding="utf-8", errors="replace") as f:
        segs = json.load(f)["transcription"]
    palavras, ant = [], 0.0
    for s in segs:
        for tk in s["tokens"]:
            tx, td = tk["text"], tk.get("t_dtw", -1)
            if tx.startswith("[") or tx.startswith("<|") or td < 0:
                continue
            t = td / 100
            if tx.startswith(" ") or not palavras:
                # palavra nova: começa onde o token anterior terminou
                palavras.append({"w": tx.strip(), "s": ant, "e": t})
            else:
                palavras[-1]["w"] += tx
                palavras[-1]["e"] = t
            ant = t
    for p in palavras:  # palavra que "engoliu" fala não reconhecida: início plausível pelo tamanho
        maxdur = 0.12 + 0.075 * len(p["w"])
        if p["e"] - p["s"] > maxdur:
            p["s"] = p["e"] - maxdur
    palavras = [p for p in palavras if p["w"] and any(c.isalnum() for c in p["w"])]
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(palavras, f, ensure_ascii=False)

    # frases legíveis: quebra em pontuação final ou pausa > 0.7s
    linhas, atual = [], []
    for i, p in enumerate(palavras):
        atual.append(p)
        prox = palavras[i + 1] if i + 1 < len(palavras) else None
        if p["w"][-1] in ".?!" or prox is None or prox["s"] - p["e"] > 0.7:
            texto = " ".join(x["w"] for x in atual)
            linhas.append(f"[{fmt(atual[0]['s'])} - {fmt(atual[-1]['e'])}] {texto}")
            atual = []
    with open(os.path.join(pasta, "transcricao.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    os.remove(wav)
    print(f"Pronto: {pasta} ({len(palavras)} palavras, {len(linhas)} frases)")


if __name__ == "__main__":
    main()
