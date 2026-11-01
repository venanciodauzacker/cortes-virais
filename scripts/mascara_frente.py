"""Máscara "frente" do henrico pro: cabeça + mãos/braços (pele) ficam na frente do texto; a camisa não.
Uso: /usr/bin/python3 mascara_frente.py <pasta_quadros_jpg> <pasta_mascaras_png> <pasta_saida>
(precisa de numpy: roda no python do sistema)"""
import subprocess, sys, os
import numpy as np

q, m, out = sys.argv[1:4]
W, H = 456, 256
os.makedirs(out, exist_ok=True)
n = len([f for f in os.listdir(q) if f.endswith(".jpg")])


def ler(padrao, fmt, c):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", padrao, "-vf", f"scale={W}:{H}", "-f", "rawvideo",
                          "-pix_fmt", fmt, "-"], stdout=subprocess.PIPE)
    while True:
        b = p.stdout.read(W * H * c)
        if len(b) < W * H * c:
            return
        yield np.frombuffer(b, np.uint8).reshape(H, W, c) if c > 1 else np.frombuffer(b, np.uint8).reshape(H, W)


def caixa(a, r):
    """média numa janela (2r+1)^2 via soma acumulada"""
    s = np.pad(a.astype(np.float32), r + 1, mode="edge").cumsum(0).cumsum(1)
    k = 2 * r + 1
    return (s[k:, k:] - s[:-k, k:] - s[k:, :-k] + s[:-k, :-k])[:H, :W] / (k * k)


sai = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}",
                        "-r", "30", "-i", "-", os.path.join(out, "%05d.png")], stdin=subprocess.PIPE)
ombro_ant = None
for img, mk in zip(ler(os.path.join(q, "%05d.jpg"), "yuv444p", 3) if False else ler(os.path.join(q, "%05d.jpg"), "rgb24", 3),
                   ler(os.path.join(m, "%05d.png"), "gray", 1)):
    p = mk > 127
    larg = p.sum(1)
    linhas = np.nonzero(larg > 6)[0]
    f = np.zeros((H, W), bool)
    if len(linhas):
        topo = linhas[0]
        cab = np.median(larg[topo:topo + max(8, int(H * 0.12))])
        ombro = next((y for y in range(topo + 10, H) if larg[y] > 1.9 * cab), H)
        # suaviza o ombro entre quadros (evita a linha pular)
        ombro = ombro if ombro_ant is None else int(0.6 * ombro_ant + 0.4 * ombro)
        ombro_ant = ombro
        f[:ombro] = p[:ombro]
        r, g, b = [img[..., i].astype(np.int16) for i in range(3)]
        y = 0.299 * r + 0.587 * g + 0.114 * b
        cr = 128 + 0.5 * r - 0.4187 * g - 0.0813 * b
        cb = 128 - 0.1687 * r - 0.3313 * g + 0.5 * b
        pele = (cr > 133) & (cr < 180) & (cb > 75) & (cb < 130) & (y > 55)
        pele = caixa(pele, 2) > 0.5          # tira pontinhos soltos
        f[ombro:] = p[ombro:] & pele[ombro:]
    f = (caixa(f, 1) > 0.5).astype(np.uint8) * 255
    sai.stdin.write(f.tobytes())
sai.stdin.close()
sai.wait()
print("ok", len(os.listdir(out)))
