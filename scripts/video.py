"""Image generation for cat animation frames."""
import os
import time
import urllib.parse

import requests

IMAGE_WIDTH = 1080
IMAGE_HEIGHT = 1920
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "flux")
IMAGE_TIMEOUT = int(os.getenv("IMAGE_TIMEOUT", "240"))
IMAGE_RETRIES = int(os.getenv("IMAGE_RETRIES", "3"))


def pollinations_image(prompt, out_path, seed=None):
    """Generate one image."""
    clean = " ".join(prompt.split())[:1500]
    encoded = urllib.parse.quote(clean)
    if seed is None:
        seed = int(time.time())
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={IMAGE_WIDTH}&height={IMAGE_HEIGHT}"
        f"&model={IMAGE_MODEL}"
        f"&nologo=true&enhance=true&safe=true"
        f"&seed={seed}"
    )
    for attempt in range(1, IMAGE_RETRIES + 1):
        try:
            r = requests.get(url, timeout=IMAGE_TIMEOUT)
            if r.status_code == 200 and r.content and len(r.content) > 5000:
                with open(out_path, "wb") as f:
                    f.write(r.content)
                return True
            print(f"  HTTP {r.status_code}, retry {attempt}")
        except Exception as exc:
            print(f"  Image err: {str(exc)[:100]}")
        time.sleep(4)
    return False


def generate_scene_frames(prompt_fn, scene_index, n_frames, out_dir, base_seed=0):
    """Generate N frames for one scene."""
    frames = []
    for f in range(n_frames):
        fp = os.path.join(out_dir, f"scene_{scene_index}_frame_{f}.jpg")
        seed = base_seed + scene_index * 1000 + f
        if pollinations_image(prompt_fn(f), fp, seed=seed):
            frames.append(fp)
            print(f"  Frame {f+1}/{n_frames} OK")
        else:
            print(f"  Frame {f+1}/{n_frames} FAILED")
            if frames:
                frames.append(frames[-1])
    return frames
