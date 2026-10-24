"""Pós-produção do clipe gerado por IA (pantera -> Volkswagen).

1. Conforma o clipe para 1080x1920, 24 fps (cover crop, sem distorção).
2. Alinha cada quadro ao plate (foto original) por ECC euclidiano, estimado só na área travada
   (teto/piso), com suavização temporal -> elimina deriva de câmera do gerador.
3. Correspondência de cor da zona de ação com o plate (ganho por canal, suavizado no tempo).
4. Travamento da garagem: fora da máscara, os pixels vêm do plate original (cenário intocado).
5. Registro do quadro final: nos últimos K quadros o carro gerado converge ao carro da foto
   (K pequeno; só corrige resíduo de geometria/cor — não substitui a transformação).
6. Codifica H.264 (yuv420p, BT.709, faststart) + áudio AAC e gera relatório de QC.

Uso:
  python3 -I pos_producao.py --gerado clip.mp4 --plate plate.png --mascara mascara.png \
      --audio audio.wav --saida Volkswagen_Pantera_Transformacao_Cinematografica.mp4
"""
import argparse
import json
import subprocess
import sys

import cv2
import numpy as np

W, H = 1080, 1920


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=width,height,r_frame_rate:format=duration', '-of', 'json', path],
                         check=True, capture_output=True, text=True).stdout
    j = json.loads(out)
    s = j['streams'][0]
    num, den = map(int, s['r_frame_rate'].split('/'))
    return s['width'], s['height'], num / den, float(j['format']['duration'])


def read_frames(path, fps, retime):
    vf = f'scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}'
    if retime != 1.0:
        vf = f'setpts={retime:.6f}*PTS,' + vf
    vf += f',fps={fps}'
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-vf', vf, '-f', 'rawvideo',
                          '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
    n = W * H * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
    p.wait()


def ecc_align(frame_g, plate_g, lock_mask, warp_init):
    warp = warp_init.copy()
    try:
        _, warp = cv2.findTransformECC(plate_g, frame_g, warp, cv2.MOTION_EUCLIDEAN,
                                       (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-5),
                                       lock_mask, 5)
        return warp, True
    except cv2.error:
        return warp_init, False


def smoothstep(u):
    u = np.clip(u, 0, 1)
    return u * u * (3 - 2 * u)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gerado', required=True, help='clipe gerado pela IA (quadro inicial = pantera, final = plate)')
    ap.add_argument('--plate', required=True)
    ap.add_argument('--mascara', required=True, help='branco = zona de ação; preto = garagem travada no plate')
    ap.add_argument('--audio')
    ap.add_argument('--saida', required=True)
    ap.add_argument('--fps', type=int, default=24)
    ap.add_argument('--duracao', type=float, default=10.0, help='duração alvo (s) quando --ajustar-duracao')
    ap.add_argument('--ajustar-duracao', action='store_true',
                    help='reescala o tempo do clipe para --duracao (ex.: clipe de 8 s -> 10 s)')
    ap.add_argument('--sem-alinhamento', action='store_true')
    ap.add_argument('--sem-travamento', action='store_true')
    ap.add_argument('--quadros-registro-final', type=int, default=6)
    ap.add_argument('--qc', default=None, help='prefixo dos arquivos de QC (padrão: saída sem .mp4)')
    a = ap.parse_args()

    sw, sh, sfps, sdur = probe(a.gerado)
    retime = a.duracao / sdur if a.ajustar_duracao else 1.0
    print(f'entrada {sw}x{sh} {sfps:.3f} fps {sdur:.2f}s  retime x{retime:.3f}', file=sys.stderr)

    plate = cv2.imread(a.plate)
    assert plate.shape == (H, W, 3), plate.shape
    m = cv2.imread(a.mascara, cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
    m3 = m[..., None]
    sc = 0.25  # alinhamento em 1/4 de resolução, aplicado em resolução cheia
    plate_g = cv2.GaussianBlur(cv2.cvtColor(cv2.resize(plate, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA),
                                            cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 1.0)
    lock_small = (cv2.resize(m, (plate_g.shape[1], plate_g.shape[0])) < 0.05).astype(np.uint8)
    ring = (m > 0.15) & (m < 0.6)  # faixa de transição para medir diferença de cor gerado x plate
    plate_ring = plate[ring].astype(np.float64).mean(0)

    frames = list(read_frames(a.gerado, a.fps, retime))
    n = len(frames)
    assert n > 2 * a.fps, f'clipe curto demais: {n} quadros'
    print(f'{n} quadros a {a.fps} fps ({n / a.fps:.2f}s)', file=sys.stderr)

    # passo 1: alinhamento (ECC) de cada quadro ao plate + suavização temporal
    warps, ok = [], 0
    w_prev = np.eye(2, 3, dtype=np.float32)
    for f in frames:
        if a.sem_alinhamento:
            warps.append(np.eye(2, 3, dtype=np.float32))
            continue
        fg = cv2.GaussianBlur(cv2.cvtColor(cv2.resize(f, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA),
                                           cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 1.0)
        w_prev, good = ecc_align(fg, plate_g, lock_small, w_prev)
        ok += good
        warps.append(w_prev.copy())
    P = np.array([[np.arctan2(w[1, 0], w[0, 0]), w[0, 2] / sc, w[1, 2] / sc] for w in warps])
    k = np.ones(5) / 5
    Ps = np.stack([np.convolve(np.pad(P[:, i], 2, mode='edge'), k, 'valid') for i in range(3)], 1)

    # passo 2: composição
    enc = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}',
           '-r', str(a.fps), '-i', '-']
    if a.audio:
        enc += ['-i', a.audio, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '192k', '-shortest']
    enc += ['-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
            '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
            '-movflags', '+faststart', a.saida]
    pe = subprocess.Popen(enc, stdin=subprocess.PIPE)
    gain_s = np.ones(3)
    shifts, seam, out_frames = [], [], {}
    qc_t = [0, 2, 4, 5, 6, 7.5, (n - 1) / a.fps]
    qc_idx = {min(n - 1, round(t * a.fps)): t for t in qc_t}
    prev_zone = None
    flicker = []
    for i, f in enumerate(frames):
        th, tx, ty = Ps[i]
        wm = np.array([[np.cos(th), -np.sin(th), tx], [np.sin(th), np.cos(th), ty]], np.float32)
        shifts.append(float(np.hypot(tx, ty)))
        g = cv2.warpAffine(f, wm, (W, H), flags=cv2.INTER_LANCZOS4 | cv2.WARP_INVERSE_MAP,
                           borderMode=cv2.BORDER_REFLECT).astype(np.float32)
        if not a.sem_travamento:
            gain = plate_ring / np.maximum(g[ring].astype(np.float64).mean(0), 1)
            gain_s = 0.85 * gain_s + 0.15 * np.clip(gain, 0.8, 1.25) if i else np.clip(gain, 0.8, 1.25)
            g *= gain_s[None, None, :].astype(np.float32)
            o = m3 * g + (1 - m3) * plate
            seam.append(float(np.abs(g[ring] - plate[ring]).mean()))
        else:
            o = g
        kf = a.quadros_registro_final
        if i == n - kf - 1:
            pre = o.astype(np.float64)
        if kf > 0 and i >= n - kf:
            al = smoothstep((i - (n - kf) + 1) / kf)
            o = (1 - al) * o + al * plate
        o = np.clip(o + 0.5, 0, 255).astype(np.uint8)
        zone = cv2.cvtColor(o, cv2.COLOR_BGR2GRAY)[m > 0.5].astype(np.float32).mean()
        if prev_zone is not None:
            flicker.append(abs(zone - prev_zone))
        prev_zone = zone
        if i in qc_idx:
            out_frames[qc_idx[i]] = o
        pe.stdin.write(o.tobytes())
    pe.stdin.close()
    pe.wait()

    # QC
    qc = a.qc or a.saida.rsplit('.', 1)[0]
    tiles = []
    for t in qc_t:
        im = cv2.resize(out_frames[t], (360, 640), interpolation=cv2.INTER_AREA)
        cv2.putText(im, f'{t:.1f}s', (12, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2, cv2.LINE_AA)
        tiles.append(im)
    tiles.append(cv2.resize(plate, (360, 640), interpolation=cv2.INTER_AREA))
    cv2.putText(tiles[-1], 'foto', (12, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.imwrite(qc + '_qc.jpg', np.vstack([np.hstack(tiles[:4]), np.hstack(tiles[4:])]),
                [cv2.IMWRITE_JPEG_QUALITY, 88])
    last = out_frames[qc_t[-1]].astype(np.float64)
    psnr = lambda x: 10 * np.log10(255 ** 2 / max(np.mean((x - plate) ** 2), 1e-9))
    rep = {
        'quadros': n, 'duracao_s': round(n / a.fps, 3), 'fps': a.fps,
        'alinhamento_ecc_convergiu': f'{ok}/{n}' if not a.sem_alinhamento else 'desligado',
        'deriva_camera_corrigida_px_max': round(max(shifts), 2),
        'costura_zona_acao_erro_medio': round(float(np.mean(seam)), 2) if seam else None,
        'flicker_zona_acao_max_delta_luma': round(float(np.max(flicker)), 2),
        'psnr_quadro_final_vs_foto_db': round(psnr(last), 2),
        'psnr_gerado_antes_do_registro_final_db': round(psnr(pre), 2),
    }
    json.dump(rep, open(qc + '_qc.json', 'w'), indent=2, ensure_ascii=False)
    print(json.dumps(rep, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
