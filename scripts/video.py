"""Scene clip generation: Replicate first, Pollinations image + zoom as fallback."""
import os
import subprocess
from urllib.parse import quote

import requests

CLIP_SECONDS = int(os.getenv("CLIP_SECONDS", "5"))
# Comma separated, tried in order. Change without touching code.
VIDEO_MODELS = [m.strip() for m in os.getenv(
    "VIDEO_MODELS", "bytedance/seedance-1-lite,minimax/video-01").split(",") if m.strip()]


def _inputs(model, prompt):
    if model.startswith("bytedance/seedance"):
        full = {"prompt": prompt, "duration": CLIP_SECONDS, "resolution": "720p",
                "aspect_ratio": "9:16", "fps": 24}
    elif model.startswith("minimax/"):
        full = {"prompt": prompt, "prompt_optimizer": True}
    else:
        full = {"prompt": prompt, "aspect_ratio": "9:16"}
    return [full, {"prompt": prompt}]  # second = bare minimum if params are rejected


def _save(output, path):
    if isinstance(output, (list, tuple)):
        output = output[0]
    if hasattr(output, "read"):
        data = output.read()
    else:
        r = requests.get(str(output), timeout=300)
        r.raise_for_status()
        data = r.content
    with open(path, "wb") as f:
        f.write(data)


def replicate_clip(prompt, path):
    if not os.getenv("REPLICATE_API_TOKEN"):
        return False
    import replicate
    for model in VIDEO_MODELS:
        for inp in _inputs(model, prompt):
            try:
                print(f"  Replicate {model} ...")
                _save(replicate.run(model, input=inp), path)
                return True
            except Exception as exc:  # noqa: BLE001
                print(f"  {model} failed: {str(exc)[:200]}")
    return False


def pollinations_clip(prompt, path, seed):
    """Free fallback: one generated image with a slow zoom. Less lively but never fails the run."""
    key = os.getenv("POLLINATIONS_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        r = requests.get(
            "https://image.pollinations.ai/prompt/" + quote(prompt),
            params={"width": 720, "height": 1280, "model": "flux", "nologo": "true", "seed": seed},
            headers=headers, timeout=180)
        r.raise_for_status()
        img = path + ".jpg"
        with open(img, "wb") as f:
            f.write(r.content)
        frames = CLIP_SECONDS * 25
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", img, "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"zoompan=z='min(zoom+0.0012,1.2)':d={frames}:s=1080x1920:fps=25",
            "-frames:v", str(frames), "-pix_fmt", "yuv420p", path], check=True)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  Pollinations failed: {str(exc)[:200]}")
        return False


def make_clip(prompt, path, seed=0):
    if replicate_clip(prompt, path):
        return True
    print("  Falling back to Pollinations image + zoom")
    return pollinations_clip(prompt, path, seed)
