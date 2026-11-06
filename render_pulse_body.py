#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from threading import Thread

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


W, H = 720, 1280
FPS = 30
DEFAULT_SOURCE = Path(__file__).resolve().parent / "assets" / "reve_labs_pixel_body.png"
DEFAULT_LABEL = "REVE LABS SOUND"


def find_ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise RuntimeError("ffmpeg not found. Install ffmpeg and make sure it is available on PATH.")


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def prepare_wav(audio_path: Path, workdir: Path, ffmpeg: str) -> Path:
    if audio_path.suffix.lower() == ".wav":
        return audio_path
    wav_path = workdir / "input_audio.wav"
    run([ffmpeg, "-y", "-i", str(audio_path), "-ac", "2", "-ar", "48000", str(wav_path)])
    return wav_path


def load_audio(path: Path, max_duration: float | None = None):
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        channels = wf.getnchannels()
        frames = wf.getnframes()
        if max_duration:
            frames = min(frames, int(max_duration * sr))
        data = wf.readframes(frames)
    arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    if channels > 1:
        arr = arr.reshape(-1, channels).mean(axis=1)
    return arr / 32768.0, sr


def normalize(x, lo_p=5, hi_p=97):
    x = np.asarray(x, dtype=np.float32)
    lo, hi = np.percentile(x, lo_p), np.percentile(x, hi_p)
    if hi <= lo:
        return np.zeros_like(x)
    return np.clip((x - lo) / (hi - lo), 0, 1)


def ema(x, alpha):
    out = np.zeros_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
    return out


def audio_features(audio, sr):
    hop = int(sr / FPS)
    n = math.ceil(len(audio) / hop)
    padded = np.pad(audio, (0, max(0, n * hop - len(audio))))
    window = np.hanning(hop)
    freqs = np.fft.rfftfreq(hop, 1 / sr)
    rms, onset, low, mid, high = [], [], [], [], []
    prev = None
    for i in range(n):
        frame = padded[i * hop:(i + 1) * hop] * window
        mag = np.abs(np.fft.rfft(frame))
        rms.append(float(np.sqrt(np.mean(frame ** 2))))
        onset.append(0.0 if prev is None else float(np.maximum(mag - prev, 0).mean()))
        prev = mag
        low.append(float(mag[freqs < 220].mean()))
        mid.append(float(mag[(freqs >= 220) & (freqs < 2200)].mean()))
        high.append(float(mag[freqs >= 2200].mean()))

    rms = ema(normalize(rms), 0.12)
    onset = ema(normalize(onset, 12, 99), 0.42)
    low = ema(normalize(low), 0.11)
    mid = ema(normalize(mid), 0.16)
    high = ema(normalize(high), 0.22)
    hit = np.clip(onset * 0.82 + high * 0.22 + rms * 0.20 + low * 0.14, 0, 1)
    hit = np.sqrt(hit)
    tail = np.zeros_like(hit)
    for i in range(1, len(hit)):
        tail[i] = max(hit[i], tail[i - 1] * 0.895)
    return {"n": n, "rms": rms, "onset": onset, "low": low, "mid": mid, "high": high, "hit": hit, "tail": tail}


def fit_source(source: Path):
    src = Image.open(source).convert("RGB")
    sw, sh = src.size
    scale = max(W / sw, H / sh)
    src = src.resize((int(sw * scale), int(sh * scale)), Image.Resampling.LANCZOS)
    left = (src.width - W) // 2
    top = (src.height - H) // 2
    return src.crop((left, top, left + W, top + H))


def load_font(size, index=0):
    paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size=size, index=index)
        except Exception:
            continue
    return ImageFont.load_default()


def make_renderer(source: Path, track_title: str, album_title: str, label_name: str, archive_code: str):
    base = fit_source(source)
    yy_grid, xx_grid = np.mgrid[0:H, 0:W]
    cx, cy = 365.0, 817.0
    dist_grid = np.sqrt((xx_grid - cx) ** 2 + (yy_grid - cy) ** 2)

    font_track = load_font(28)
    font_album = load_font(15)
    font_label = load_font(11)
    font_micro = load_font(9)
    font_code = load_font(10)

    gray = np.asarray(base.convert("L"))
    yy, xx = np.where(gray < 176)
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    mask = (dist > 45) & (dist < 410) & (yy > H * 0.34) & (yy < H * 0.96)
    xx, yy, dist = xx[mask], yy[mask], dist[mask]
    rng = np.random.default_rng(1010)
    if len(xx) > 16000:
        idx = rng.choice(len(xx), 16000, replace=False)
        xx, yy, dist = xx[idx], yy[idx], dist[idx]
    tones = gray[yy, xx]
    seeds = rng.random(len(xx))
    particles = np.stack([xx, yy, tones, dist, seeds], axis=1).astype(np.float32)

    def draw_archive_ui(img, i, feat):
        t = i / FPS
        hit = float(feat["hit"][i])
        rms = float(feat["rms"][i])
        high = float(feat["high"][i])
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay, "RGBA")

        x, y = 42, 92
        draw.line((x, y - 28, x + 76, y - 28), fill=(35, 35, 33, 92), width=1)
        draw.text((x, y - 14), archive_code, fill=(54, 54, 50, 116), font=font_code)
        draw.text((x, y + 10), track_title, fill=(35, 35, 33, 226), font=font_track)
        draw.text((x, y + 48), album_title, fill=(78, 78, 74, 148), font=font_album)
        draw.text((x, y + 75), label_name, fill=(68, 68, 64, 132), font=font_label)

        strip_y = y + 116
        for b in range(54):
            bx = x + b * 5
            phase = b * 0.37 + t * 2.2
            amp = 3.5 + 13.0 * (0.5 + 0.5 * math.sin(phase)) * (0.55 + rms * 0.75)
            amp += hit * (2.0 + 5.0 * math.sin(b * 0.91 + t * 7.0) ** 2)
            alpha = int(54 + 42 * high + 18 * hit)
            draw.line((bx, strip_y - amp / 2, bx, strip_y + amp / 2), fill=(48, 48, 45, alpha), width=1)
        elapsed = min(t, 99.0)
        draw.text((x + 296, strip_y - 8), f"00:{elapsed:05.2f}", fill=(82, 82, 78, 92), font=font_micro)

        rx = W - 54
        draw.line((rx, 122, rx, 382), fill=(40, 40, 38, 36), width=1)
        for j, lab in enumerate(["01", "02", "03", "04"]):
            y_tick = 134 + j * 64
            tick = 5 + (2 if j == 3 and hit > 0.52 else 0)
            draw.line((rx - tick, y_tick, rx + tick, y_tick), fill=(40, 40, 38, 52), width=1)
            draw.text((rx + 10, y_tick - 6), lab, fill=(70, 70, 66, 72), font=font_micro)
        draw.text((rx - 27, 410), "SOUND\nCODE", fill=(70, 70, 66, 60), font=font_micro, spacing=2)

        for mark_x, mark_y, sx, sy in [
            (34, 72, 22, 22),
            (W - 34, 72, -22, 22),
            (34, H - 66, 22, -22),
            (W - 34, H - 66, -22, -22),
        ]:
            draw.line((mark_x, mark_y, mark_x + sx, mark_y), fill=(32, 32, 30, 34), width=1)
            draw.line((mark_x, mark_y, mark_x, mark_y + sy), fill=(32, 32, 30, 34), width=1)

        return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    def base_arr(i, feat):
        t = i / FPS
        tail = float(feat["tail"][i])
        high = float(feat["high"][i])
        scale = 1.0 + 0.0025 * tail
        src = base.resize((int(W * scale), int(H * scale)), Image.Resampling.BICUBIC)
        img = Image.new("RGB", (W, H), (235, 233, 228))
        img.paste(src, ((W - src.width) // 2, (H - src.height) // 2))
        arr = np.asarray(img).astype(np.float32)
        rng = np.random.default_rng(i)
        paper = 2.4 * np.sin(xx_grid * 0.004 + t * 0.18) + 1.8 * np.cos(yy_grid * 0.005 - t * 0.12)
        arr += paper[..., None]
        arr += rng.normal(0, 1.10 + high * 1.9, arr.shape)
        return arr

    def render_frame(i, feat):
        t = i / FPS
        hit = float(feat["hit"][i])
        tail = float(feat["tail"][i])
        high = float(feat["high"][i])
        rng = np.random.default_rng(i)
        arr = base_arr(i, feat)

        lens = np.exp(-(dist_grid ** 2) / (2 * (192 + tail * 58) ** 2))
        amount = 0.020 + 0.070 * tail + 0.030 * hit
        sx = np.clip((xx_grid - (xx_grid - cx) * lens * amount).astype(np.int32), 0, W - 1)
        sy = np.clip((yy_grid - (yy_grid - cy) * lens * amount).astype(np.int32), 0, H - 1)
        arr = arr[sy, sx]

        inner = np.exp(-(dist_grid ** 2) / (2 * (58 + tail * 18) ** 2))
        dense = np.exp(-((dist_grid - (92 + tail * 24)) ** 2) / (2 * (42 + hit * 20) ** 2))
        arr += inner[..., None] * (14 + 46 * hit)
        arr -= dense[..., None] * (6 + 16 * tail)

        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
        draw = ImageDraw.Draw(img, "RGBA")

        wave_radius = 102 + 120 * tail
        wave_width = 38 + 38 * hit
        influence = 280 + 90 * tail
        for x, y, tone, dist, seed in particles:
            dx, dy = x - cx, y - cy
            d = math.sqrt(dx * dx + dy * dy) + 1e-6
            wave = math.exp(-((d - wave_radius) ** 2) / (2 * wave_width ** 2))
            gravity = math.exp(-((d / influence) ** 2))
            if wave < 0.022 and gravity < 0.035:
                continue
            pull = gravity * (8 + 32 * tail)
            push = wave * (22 + 48 * hit)
            orbit = (1.0 + high * 5.0) * math.sin(t * 14 + seed * 37)
            angle = seed * math.tau
            px = x - (dx / d) * pull + (dx / d) * push + math.cos(angle + t * 2.0) * orbit
            py = y - (dy / d) * pull + (dy / d) * push + math.sin(angle + t * 1.6) * orbit
            val = int(max(10, min(230, tone - 18 * wave - 10 * gravity + 16 * hit * wave)))
            alpha = int(38 + 130 * wave + 58 * gravity)
            r = 1 + (1 if wave > 0.46 else 0)
            draw.ellipse([px - r, py - r, px + r, py + r], fill=(val, val, val, min(220, alpha)))

        ripple = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        rd = ImageDraw.Draw(ripple, "RGBA")
        for ring, base_r in enumerate([112, 174, 242]):
            rr = base_r + tail * (22 + ring * 20)
            alpha = int(8 + 30 * hit - ring * 5)
            if alpha <= 0:
                continue
            pts = []
            for k in range(180):
                a = k * math.tau / 180
                wobble = math.sin(a * (4 + ring) + t * 1.1 + ring) * (5 + 18 * tail)
                pts.append((cx + math.cos(a) * (rr + wobble), cy + math.sin(a) * (rr + wobble)))
            rd.line(pts + [pts[0]], fill=(44, 44, 42, alpha), width=1)
        img = Image.alpha_composite(img, ripple.filter(ImageFilter.GaussianBlur(0.75 + hit * 0.55)))

        shimmer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shimmer, "RGBA")
        for _ in range(150 + int(230 * hit)):
            a = rng.uniform(0, math.tau)
            rr = rng.normal(78 + tail * 34, 28 + hit * 22)
            x = cx + math.cos(a) * rr
            y = cy + math.sin(a) * rr
            val = int(rng.uniform(20, 112))
            sd.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(val, val, val, 50 + int(72 * hit)))
        img = Image.alpha_composite(img, shimmer.filter(ImageFilter.GaussianBlur(0.15)))
        img = img.convert("RGB").filter(ImageFilter.GaussianBlur(0.04))
        return draw_archive_ui(img, i, feat)

    return render_frame


def encode(frames_dir: Path, audio_path: Path, out_path: Path, duration: float, ffmpeg: str, crf: int):
    run([
        ffmpeg,
        "-y",
        "-framerate",
        str(FPS),
        "-i",
        str(frames_dir / "frame_%04d.png"),
        "-i",
        str(audio_path),
        "-t",
        f"{duration:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(out_path),
    ])


def encode_stream(render_frame, feat, audio_path: Path, out_path: Path, duration: float, ffmpeg: str, crf: int):
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-i",
        str(audio_path),
        "-t",
        f"{duration:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert process.stdin is not None
    try:
        for i in range(feat["n"]):
            frame = render_frame(i, feat).convert("RGB")
            process.stdin.write(frame.tobytes())
            if i % 15 == 0:
                print(f"{i}/{feat['n']}", flush=True)
    finally:
        process.stdin.close()
    code = process.wait()
    if code != 0:
        raise subprocess.CalledProcessError(code, cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render an audio-reactive Pulse Body video.")
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--track-title", default="Untitled Track")
    parser.add_argument("--album-title", default="Sound Field Study")
    parser.add_argument("--label-name", default=DEFAULT_LABEL)
    parser.add_argument("--archive-code", default="RLS-PBH-001 / SOUND FIELD STUDY")
    parser.add_argument("--max-duration", type=float, default=None, help="Optional preview duration in seconds.")
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--keep-frames", action="store_true")
    parser.add_argument("--stream", action="store_true", help="Encode frames directly to ffmpeg without saving PNG frames.")
    args = parser.parse_args()

    ffmpeg = find_ffmpeg()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="reve_pixel_body_") as tmp:
        workdir = Path(tmp)
        frames_dir = workdir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        wav_audio = prepare_wav(args.audio, workdir, ffmpeg)
        audio, sr = load_audio(wav_audio, args.max_duration)
        feat = audio_features(audio, sr)
        duration = len(audio) / sr
        render_frame = make_renderer(args.source, args.track_title, args.album_title, args.label_name, args.archive_code)
        if args.stream:
            encode_stream(render_frame, feat, wav_audio, args.output, duration, ffmpeg, args.crf)
        else:
            for i in range(feat["n"]):
                render_frame(i, feat).save(frames_dir / f"frame_{i:04d}.png", quality=94)
                if i % 15 == 0:
                    print(f"{i}/{feat['n']}", flush=True)
            encode(frames_dir, wav_audio, args.output, duration, ffmpeg, args.crf)
        if args.keep_frames:
            saved = args.output.parent / f"{args.output.stem}_frames"
            if saved.exists():
                shutil.rmtree(saved)
            shutil.copytree(frames_dir, saved)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
