"""Image generation + cinematic motion clips."""
import os
import subprocess
import time
import urllib.parse

import requests

IMAGE_WIDTH = 1080
IMAGE_HEIGHT = 1920
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "flux-realism")   # realistic model
IMAGE_TIMEOUT = 180
IMAGE_RETRIES = 4
CLIP_SECONDS = int(os.getenv("CLIP_SECONDS", "5"))


def pollinations_image(prompt, out_path, seed=None):
    """Generate ONE realistic image via Pollinations (free, no key)."""
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
                print(f"    Image OK ({len(r.content)//1024} KB)")
                return True
            print(f"    Image HTTP {r.status_code}, retry {attempt}")
        except Exception as exc:
            print(f"    Image err: {str(exc)[:100]}")
        time.sleep(4)
    return False


def make_motion_clip(image_path, out_path, scene_idx=0, duration=5):
    """Turn a still image into a cinematic motion clip.

    Uses slow zoom + subtle pan for a cinematic feel.
    Alternates direction per scene for variety.
    """
    fps = 30
    frames = duration * fps

    # Cinematic slow zoom - very subtle, no jarring
    # Alternating: even scenes zoom IN, odd scenes zoom OUT
    if scene_idx % 2 == 0:
        z_expr = "min(zoom+0.0008,1.15)"   # slow zoom in, max 15%
    else:
        z_expr = "max(1.15-0.0008*on,1.0)"  # slow zoom out

    # Tiny pan offsets for cinematic feel
    if scene_idx % 4 == 0:
        x_expr = "iw/2-(iw/zoom/2)+on*0.4"
        y_expr = "ih/2-(ih/zoom/2)"
    elif scene_idx % 4 == 1:
        x_expr = "iw/2-(iw/zoom/2)-on*0.4"
        y_expr = "ih/2-(ih/zoom/2)"
    elif scene_idx % 4 == 2:
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)-on*0.4"
    else:
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)+on*0.4"

    vf = (
        "scale=1188:2112:force_original_aspect_ratio=increase,"
        f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':"
        f"d={frames}:s=1080x1920:fps={fps},"
        "setsar=1,format=yuv420p"
    )

    try:
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-i", image_path,
            "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            out_path,
        ], check=True, timeout=240)
        print(f"    Motion clip OK")
        return True
    except Exception as exc:
        print(f"    Motion err: {str(exc)[:150]}")
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
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
                   "pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            out_path,
        ], check=True, timeout=180)
        return True
    except Exception:
        return False
