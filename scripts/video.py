"""Video clip builder for the YouTube Shorts bot.

Approach: generate ONE high-quality 3D Pixar-style image per scene
(Pollinations - free, no API key needed), then FFmpeg creates a
Ken Burns motion clip from it. This gives us:
  - consistent character look
  - reliable generation (no 503/429 rate limits)
  - controllable cinematic motion
  - acceptable quality for YouTube Shorts
"""

import os
import time
import urllib.parse

import requests

CLIP_SECONDS = int(os.getenv("CLIP_SECONDS", "5"))

# Image generation settings
IMAGE_WIDTH = 1080
IMAGE_HEIGHT = 1920
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "flux")  # flux | turbo | any
IMAGE_TIMEOUT = int(os.getenv("IMAGE_TIMEOUT", "180"))
IMAGE_RETRIES = int(os.getenv("IMAGE_RETRIES", "3"))


def _clean_prompt(prompt: str) -> str:
    """Trim and compact the prompt for URL encoding."""
    prompt = " ".join(prompt.split())
    return prompt[:900]


def pollinations_image(prompt: str, out_path: str) -> bool:
    """Generate one 1080x1920 image via Pollinations (free, no key).

    Returns True and writes the JPG to out_path on success.
    Retries a few times because the free tier occasionally 5xx's.
    """
    clean = _clean_prompt(prompt)
    encoded = urllib.parse.quote(clean)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={IMAGE_WIDTH}&height={IMAGE_HEIGHT}"
        f"&model={IMAGE_MODEL}&nologo=true&enhance=true"
        f"&seed={int(time.time())}"
    )

    for attempt in range(1, IMAGE_RETRIES + 1):
        try:
            print(f"  Image attempt {attempt}/{IMAGE_RETRIES}...")
            r = requests.get(url, timeout=IMAGE_TIMEOUT)
            if r.status_code == 200 and r.content and len(r.content) > 5000:
                with open(out_path, "wb") as f:
                    f.write(r.content)
                print(f"  Image OK ({len(r.content) // 1024} KB)")
                return True
            print(f"  HTTP {r.status_code}, retrying...")
        except Exception as exc:  # noqa: BLE001
            print(f"  Image error: {str(exc)[:150]}")
        time.sleep(5)

    return False


def make_clip(prompt: str, path: str, seed: int = 0) -> bool:
    """Generate ONE scene image.

    Despite the name (kept for compatibility with main.py), this now
    produces a still image rather than an mp4. assemble.py will turn
    the image into a motion clip.
    """
    print(f"Generating scene image: {path}")

    # path ends with .mp4 - save the image alongside it
    img_path = path.rsplit(".", 1)[0] + ".jpg"

    if pollinations_image(prompt, img_path):
        # Rename marker: return the image path to main.py via convention.
        # main.py reads the .jpg next to the .mp4 path.
        return True

    print("  Image generation failed for this scene.")
    return False
