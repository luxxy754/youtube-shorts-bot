"""Image generation + motion clip creation for pet drama shorts."""
import os
import subprocess
import time
import urllib.parse

import requests

IMAGE_WIDTH = 720
IMAGE_HEIGHT = 1280
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "flux")
IMAGE_TIMEOUT = 120
IMAGE_RETRIES = 3
CLIP_SECONDS = int(os.getenv("CLIP_SECONDS", "4"))


def pollinations_image(prompt, out_path, seed=None):
    """Generate ONE image via Pollinations (free, no key)."""
    clean = " ".join(prompt.split())[:1200]
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
            print(f"    Image HTTP {r.status_code}, retry {attempt}")
        except Exception as exc:
            print(f"    Image err: {str(exc)[:100]}")
        time.sleep(3)
    return False


def make_motion_clip(image_path, out_path, scene_idx=0, duration=4):
    """Turn a still image into a motion clip with Ken Burns effect."""
    # Alternate zoom direction per scene
    if scene_idx % 2 == 0:
        z_expr = "min(zoom+0.0015,1.25)"
    else:
        z_expr = "max(1.25-0.0015*on,1.0)"

    fps = 30
    frames = duration * fps

    vf = (
        "scale=792:1408:force_original_aspect_ratio=increase,"
        f"zoompan=z='{z_expr}':"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s=720x1280:fps={fps},"
        "setsar=1,format=yuv420p"
    )

    try:
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-i", image_path,
            "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            out_path,
        ], check=True, timeout=180)
        return True
    except Exception as exc:
        print(f"    Motion clip err: {str(exc)[:150]}")
        return False


def static_video(image_path, audio_path, out_path):
    """Fallback: static image + audio."""
    try:
        dur = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nk=1:nw=1", audio_path], text=True).strip()
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-i", image_path, "-i", audio_path,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
            "-t", str(dur), "-shortest",
            "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,"
                   "pad=720:1280:(ow-iw)/2:(oh-ih)/2",
            out_path,
        ], check=True, timeout=180)
        return True
    except Exception:
        return False
