"""Desenho de som procedural (10 s, 48 kHz, estéreo) para a transformação pantera -> Volkswagen.

Camadas: ambiente de garagem (rumble + zumbido de fluorescente 120 Hz + ar), servos com
aceleração/desaceleração suaves, passos metálicos, hidráulica, catracas, deslizamento de painéis,
travamentos pesados e acionamento dos faróis. Reverb de concreto por convolução com IR sintética.
Uso: python3 sound_design.py saida.wav
"""
import sys
import numpy as np
from scipy import signal

SR = 48000
DUR = 10.0
N = int(SR * DUR)
rng = np.random.default_rng(450745)
L = np.zeros(N)
R = np.zeros(N)


def bp(x, lo, hi, order=4):
    return signal.sosfilt(signal.butter(order, [lo, hi], 'bandpass', fs=SR, output='sos'), x)


def lp(x, f, order=4):
    return signal.sosfilt(signal.butter(order, f, 'lowpass', fs=SR, output='sos'), x)


def hp(x, f, order=4):
    return signal.sosfilt(signal.butter(order, f, 'highpass', fs=SR, output='sos'), x)


def smooth(u):
    """Rampa 0..1 com aceleração e desaceleração (smootherstep)."""
    u = np.clip(u, 0, 1)
    return u * u * u * (u * (u * 6 - 15) + 10)


def place(x, t0, gain=1.0, pan=0.0):
    """Mixa x em t0 com pan de potência constante (-1 esquerda .. +1 direita)."""
    i = int(t0 * SR)
    if i >= N:
        return
    x = x[: N - i] * gain
    a = (pan + 1) * np.pi / 4
    L[i:i + len(x)] += x * np.cos(a)
    R[i:i + len(x)] += x * np.sin(a)


def t_axis(d):
    return np.arange(int(d * SR)) / SR


def fade(x, fi=0.01, fo=0.02):
    n_i, n_o = max(1, int(fi * SR)), max(1, int(fo * SR))
    x = x.copy()
    x[:n_i] *= np.linspace(0, 1, n_i)
    x[-n_o:] *= np.linspace(1, 0, n_o)
    return x


def servo(d, f0, f1, wobble=0.004):
    t = t_axis(d)
    f = f0 + (f1 - f0) * smooth(t / d)
    f *= 1 + wobble * np.sin(2 * np.pi * 7.3 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    tone = sum(np.sin(k * ph) / k ** 1.3 for k in range(1, 9))
    gear = bp(rng.standard_normal(len(t)), 900, 3800) * (0.5 + 0.5 * np.sin(ph * 0.5) ** 2)
    env = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 0.6
    return fade((0.55 * tone + 0.35 * gear) * env, 0.02, 0.04)


def modal(f0, ratios, decays, d=1.2, amps=None):
    t = t_axis(d)
    amps = amps or [1.0 / (i + 1) for i in range(len(ratios))]
    return sum(a * np.sin(2 * np.pi * f0 * r * t + rng.uniform(0, 6.28)) * np.exp(-t / dc)
               for r, dc, a in zip(ratios, decays, amps))


def footstep():
    t = t_axis(0.9)
    thump = np.sin(2 * np.pi * (48 + 30 * np.exp(-t / 0.03)) * t) * np.exp(-t / 0.09)
    ring = modal(310, [1, 2.32, 4.25, 6.63], [0.22, 0.15, 0.09, 0.05], 0.9)
    scuff = hp(rng.standard_normal(len(t)), 700) * np.exp(-t / 0.035)
    return fade(1.0 * thump + 0.22 * ring + 0.18 * scuff, 0.001, 0.05)


def hydraulic(d, lo=1800, hi=6500):
    t = t_axis(d)
    hiss = bp(rng.standard_normal(len(t)), lo, hi)
    press = lp(rng.standard_normal(len(t)), 120) * 3
    env = np.sin(np.pi * t / d) ** 1.5
    return fade((0.5 * hiss + 0.5 * press) * env, 0.02, 0.05)


def click():
    t = t_axis(0.06)
    return bp(rng.standard_normal(len(t)), 2500, 7000) * np.exp(-t / 0.004) \
        + 0.4 * np.sin(2 * np.pi * 3400 * t) * np.exp(-t / 0.012)


def ratchet(d, rate0, rate1):
    out = np.zeros(int((d + 0.1) * SR))
    tt = 0.0
    while tt < d:
        c = click() * rng.uniform(0.6, 1.0)
        i = int(tt * SR)
        out[i:i + len(c)] += c[: len(out) - i]
        tt += 1.0 / (rate0 + (rate1 - rate0) * smooth(tt / d))
    return out


def clunk(f0=170, weight=1.0):
    t = t_axis(1.4)
    low = np.sin(2 * np.pi * (62 + 40 * np.exp(-t / 0.02)) * t) * np.exp(-t / (0.12 * weight + 0.05))
    metal = modal(f0, [1, 1.59, 2.14, 2.91, 3.83, 5.27], [0.6, 0.45, 0.35, 0.25, 0.16, 0.09], 1.4)
    tr = click()
    out = 1.1 * low * weight + 0.18 * metal
    out[:len(tr)] += 0.5 * tr
    return fade(out, 0.0005, 0.1)


def slide(d):
    t = t_axis(d)
    grit = bp(rng.standard_normal(len(t)), 1200, 4800)
    grain = lp(np.abs(rng.standard_normal(len(t))), 40)
    grain /= grain.max() + 1e-9
    fc = 600 + 900 * smooth(t / d)
    reso = np.sin(2 * np.pi * np.cumsum(fc) / SR) * 0.15
    env = np.sin(np.pi * t / d) ** 0.8
    return fade((grit * (0.4 + grain) + reso) * env, 0.01, 0.04)


def spin_up(d):
    t = t_axis(d)
    n = rng.standard_normal(len(t))
    # whoosh: ruído com banda que sobe 250 -> 1400 Hz (aplicado em blocos)
    out = np.zeros_like(n)
    blk = 2048
    for s in range(0, len(n), blk):
        u = s / len(n)
        fc = 250 + 1150 * smooth(u)
        seg = bp(n[max(0, s - 4096):s + blk], fc * 0.7, fc * 1.4, 2)[-min(blk, len(n) - s):]
        out[s:s + blk] = seg
    f = 40 + 260 * smooth(t / d)
    whirr = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3
    env = smooth(t / (d * 0.3)) * (1 - smooth((t - d * 0.7) / (d * 0.3)))
    return fade((out + whirr) * env, 0.01, 0.05)


def glass_tick():
    return fade(modal(2800, [1, 1.47, 2.39], [0.05, 0.035, 0.02], 0.25), 0.0005, 0.03)


def power_up():
    t = t_axis(0.45)
    f = 900 + 900 * smooth(t / 0.3)
    chirp = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.2) * smooth(t / 0.03)
    out = 0.25 * chirp
    c = click()
    out[:len(c)] += 0.6 * c
    return fade(out, 0.001, 0.05)


def creak(d):
    t = t_axis(d)
    f = 480 + 60 * np.sin(2 * np.pi * 5 * t) + 120 * t / d
    tone = signal.sawtooth(2 * np.pi * np.cumsum(f) / SR) * 0.2
    return fade(bp(tone + 0.3 * rng.standard_normal(len(t)), 350, 1600) * np.sin(np.pi * t / d), 0.02, 0.05)


# ---------------------------------------------------------------- ambiente de garagem
t = np.arange(N) / SR
brown = np.cumsum(rng.standard_normal((2, N)), axis=1)
brown = hp(lp(brown, 160), 25)
brown /= np.abs(brown).max()
hum = sum(a * np.sin(2 * np.pi * f * t) for f, a in [(120, 1), (240, 0.35), (360, 0.18), (480, 0.08)])
air = bp(rng.standard_normal((2, N)), 300, 1400)
air /= np.abs(air).max()
amb_gain = smooth(t / 0.6)
L += (0.10 * brown[0] + 0.012 * hum + 0.02 * air[0]) * amb_gain
R += (0.10 * brown[1] + 0.012 * hum + 0.02 * air[1]) * amb_gain

ev = []  # (som, t0, ganho, pan)
# 0–2 s: pantera parada, "respiração" mecânica sutil e leve giro de cabeça
ev += [(servo(1.4, 170, 210, 0.01), 0.25, 0.10, 0.1),
       (hydraulic(0.5), 0.6, 0.06, 0.2), (hydraulic(0.5), 1.45, 0.05, 0.0),
       (servo(0.4, 520, 640), 1.15, 0.09, 0.45)]
# 2–4 s: dois passos controlados e abaixamento do corpo
ev += [(footstep(), 2.40, 0.55, 0.35), (servo(0.35, 300, 420), 2.25, 0.08, 0.3),
       (footstep(), 2.95, 0.50, -0.30), (servo(0.35, 280, 400), 2.80, 0.08, -0.3),
       (hydraulic(0.75, 1500, 5000), 3.30, 0.16, 0.0), (servo(0.7, 420, 260), 3.30, 0.12, 0.0),
       (ratchet(0.45, 10, 18), 3.55, 0.05, 0.1)]
# 4–7,5 s: transformação peça por peça
ev += [  # patas dianteiras dobram -> rodas dianteiras
    (servo(0.55, 300, 720), 4.00, 0.16, 0.45), (ratchet(0.5, 14, 30), 4.02, 0.10, 0.45),
    (clunk(190, 0.8), 4.55, 0.45, 0.45), (spin_up(0.5), 4.55, 0.20, 0.4), (clunk(230, 0.6), 4.97, 0.35, 0.5),
    # patas traseiras -> rodas traseiras
    (servo(0.5, 280, 660), 4.85, 0.15, -0.45), (spin_up(0.45), 5.00, 0.18, -0.45),
    (clunk(180, 0.8), 5.35, 0.42, -0.45),
    # tronco se expande
    (hydraulic(0.6, 800, 3500), 5.30, 0.20, 0.0), (creak(0.45), 5.35, 0.12, -0.1),
    (clunk(150, 1.0), 5.60, 0.45, -0.1), (clunk(160, 0.9), 5.85, 0.40, 0.15),
    # placas deslizam: portas e para-lamas
    (slide(0.35), 5.75, 0.30, -0.25), (slide(0.30), 5.95, 0.28, 0.2), (slide(0.30), 6.10, 0.26, 0.4),
    (click(), 6.10, 0.5, -0.25), (click(), 6.25, 0.5, 0.2), (click(), 6.40, 0.5, 0.4),
    # cabeça -> grade, capô e faróis
    (ratchet(0.45, 20, 40), 6.25, 0.12, 0.55), (servo(0.5, 500, 900), 6.25, 0.13, 0.55),
    (clunk(260, 0.5), 6.55, 0.30, 0.55), (clunk(240, 0.6), 6.80, 0.32, 0.5),
    # teto e vidros
    (slide(0.3), 6.75, 0.22, -0.05), (glass_tick(), 6.95, 0.35, 0.0), (glass_tick(), 7.05, 0.30, -0.15),
    # cauda recolhe
    (servo(0.35, 700, 300), 7.00, 0.13, -0.6), (clunk(200, 0.6), 7.32, 0.33, -0.6),
    # travamentos finais
    (clunk(170, 0.9), 7.38, 0.40, -0.2), (clunk(175, 0.9), 7.44, 0.40, 0.25), (clunk(140, 1.3), 7.50, 0.62, 0.0),
]
# 7,5–10 s: revelação — suspensão assenta, faróis acendem, alívio hidráulico
ev += [(creak(0.4), 7.62, 0.10, 0.0), (power_up(), 7.78, 0.40, 0.5),
       (hydraulic(0.7, 2500, 7000), 7.95, 0.09, 0.0)]

L0, R0 = L.copy(), R.copy()
L[:] = 0
R[:] = 0
for snd, t0, g, pan in ev:
    place(snd, t0, g, pan)
dryL, dryR = L.copy(), R.copy()

# reverb de concreto (RT60 ~ 2,3 s) por IR sintética estéreo com reflexões iniciais
ir_t = t_axis(2.6)
irs = []
for ch in range(2):
    ir = rng.standard_normal(len(ir_t)) * np.exp(-6.9 * ir_t / 2.3)
    ir = lp(ir, 4500)
    for dl, a in [(0.011, 0.6), (0.023, 0.45), (0.037, 0.35), (0.052, 0.3)]:
        ir[int((dl + 0.003 * ch) * SR)] += a * 8
    ir[:int(0.008 * SR)] = 0
    irs.append(ir / np.sqrt(np.sum(ir ** 2)))
wetL = signal.fftconvolve(dryL, irs[0])[:N]
wetR = signal.fftconvolve(dryR, irs[1])[:N]
L = L0 + dryL + 0.55 * wetL
R = R0 + dryR + 0.55 * wetR

out = np.stack([L, R], 1)
out = hp(out.T, 22).T
out[-int(0.25 * SR):] *= np.linspace(1, 0, int(0.25 * SR))[:, None]
out /= np.abs(out).max()
out = np.tanh(out * 1.6) / np.tanh(1.6) * 0.89  # limitador suave, pico ~ -1 dBFS
wav = (out * 32767).astype(np.int16)

import wave
with wave.open(sys.argv[1], 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(wav.tobytes())
print('ok', sys.argv[1], wav.shape)
