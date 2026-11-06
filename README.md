# Pulse Body

Pulse Body is a local audio-reactive video renderer from REVE LABS SOUND. It turns music into a monochrome particle body whose chest core expands, refracts, disperses, and settles with the sound.

**Pixel Body Heartbeat is an original visual system created by [REVE LABS SOUND](https://revelabssound.com/).** The included digital figure is intentionally available for other artists, musicians, designers, and developers to use with attribution.

The renderer is algorithmic. It does not call a generative AI service, upload music, or consume model credits during rendering.

## How it works

At 30 frames per second, Pulse Body measures:

- RMS energy
- spectral onset
- low, mid, and high frequency energy
- a decaying pulse tail

Those features drive a locked chest-core system: radial refraction, bright core, dense annulus, particle push/pull, orbit jitter, ripple rings, and shimmer.

## Requirements

- Python 3.10+
- FFmpeg available on `PATH`

## Install

```bash
git clone https://github.com/zoezou820/reve-labs-pulse-body.git
cd reve-labs-pulse-body
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

On Windows, activate the environment with `.venv\\Scripts\\activate`.

## Run the web tool

```bash
python app.py
```

Open `http://127.0.0.1:8787`, upload audio, select a template, and render a preview or full track.

## Render from the command line

```bash
python render_pulse_body.py \
  --audio /path/to/music.wav \
  --output output.mp4 \
  --track-title "Untitled Track" \
  --album-title "Sound Field Study" \
  --label-name "REVE LABS SOUND" \
  --archive-code "RLS-PBH-001 / SOUND FIELD STUDY" \
  --stream
```

Add `--max-duration 5 --crf 23` for a quick preview.

## Use a different body image

Pass a vertical image with `--source`. Dark pixels become the particle field sampled by the motion system. For predictable placement, keep the chest core near `(365, 817)` on a 720 × 1280 canvas.

The default figure is the original REVE LABS SOUND Pixel Body Heartbeat artwork with an embedded pulse signature. A separate procedural demo body is also included and can be regenerated with:

```bash
python scripts/generate_demo_body.py
```

## Privacy

Audio stays on the computer running the tool. Uploaded files and renders are written to `outputs/`, which is excluded from Git.

## Using the digital figure

You may use and adapt the included Pixel Body Heartbeat figure under CC BY 4.0. Credit it as:

> Pixel Body Heartbeat by REVE LABS SOUND — https://revelabssound.com/

Keep the embedded REVE LABS SOUND pulse signature visible where the format allows. If a crop removes it, include the credit in the post caption, video credits, description, or project page. See [ASSET_LICENSE.md](ASSET_LICENSE.md).

REVE LABS SOUND music, release artwork, and complete logo source files are not included.

## License

Code and the procedural demo asset are available under the MIT License. The Pixel Body Heartbeat artwork is available under CC BY 4.0.

## Contributing

Small, focused improvements are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).
