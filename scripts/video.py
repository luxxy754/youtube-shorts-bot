"""Image generation (Pollinations) + Wav2Lip lipsync for talking vegetables."""
import os
import subprocess
import time
import urllib.parse

import requests

IMAGE_WIDTH = 1080
IMAGE_HEIGHT = 1920
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "flux")
IMAGE_TIMEOUT = int(os.getenv("IMAGE_TIMEOUT", "180"))
IMAGE_RETRIES = int(os.getenv("IMAGE_RETRIES", "3"))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAV2LIP_DIR = os.path.join(ROOT, "Wav2Lip")
WAV2LIP_CHECKPOINT = os.getenv(
    "WAV2LIP_CHECKPOINT",
    os.path.join(WAV2LIP_DIR, "checkpoints", "wav2lip_gan.pth"),
)


def pollinations_image(prompt: str, out_path: str) -> bool:
    """Generate one 1080x1920 Pixar-style image via Pollinations (free)."""
    clean = " ".join(prompt.split())[:900]
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
                print(f"  Image OK ({len(r.content)//1024} KB)")
                return True
            print(f"  HTTP {r.status_code}, retrying...")
        except Exception as exc:  # noqa: BLE001
            print(f"  Image error: {str(exc)[:150]}")
        time.sleep(5)
    return False


def wav2lip_sync(image_path: str, audio_path: str, out_path: str) -> bool:
    """Run Wav2Lip to make the vegetable image talk."""
    if not os.path.exists(WAV2LIP_CHECKPOINT):
        print(f"  Wav2Lip checkpoint missing: {WAV2LIP_CHECKPOINT}")
        return False
    if not os.path.exists(WAV2LIP_DIR):
        print(f"  Wav2Lip repo missing: {WAV2LIP_DIR}")
        return False

    inference_script = os.path.join(WAV2LIP_DIR, "inference.py")
    if not os.path.exists(inference_script):
        print(f"  Wav2Lip inference.py missing")
        return False

    cmd = [
        "python", inference_script,
        "--checkpoint_path", WAV2LIP_CHECKPOINT,
        "--face", image_path,
        "--audio", audio_path,
        "--outfile", out_path,
        "--pads", "0", "10", "0", "0",
        "--resize_factor", "1",
        "--nosmooth",
    ]
    try:
        print("  Running Wav2Lip...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if result.returncode != 0:
            print(f"  Wav2Lip failed: {result.stderr[-400:]}")
            return False
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            print(f"  Wav2Lip OK: {os.path.getsize(out_path)//1024} KB")
            return True
        print("  Wav2Lip output missing or too small")
        return False
    except subprocess.TimeoutExpired:
        print("  Wav2Lip timeout")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"  Wav2Lip error: {str(exc)[:200]}")
        return False


def static_video(image_path: str, audio_path: str, out_path: str) -> bool:
    """Fallback: static image + audio as video (no lipsync)."""
    try:
        # Get audio duration
        dur = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nk=1:nw=1", audio_path], text=True).strip()
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-i", image_path, "-i", audio_path,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
            "-t", dur, "-shortest",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
                   "pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            out_path,
        ], check=True, timeout=300)
        print(f"  Static video OK: {out_path}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  Static video failed: {str(exc)[:200]}")
        return False


def make_clip(prompt: str, path: str, seed: int = 0) -> bool:
    """Kept for backward compat. Not used in new pipeline."""
    img_path = path.rsplit(".", 1)[0] + ".jpg"
    return pollinations_image(prompt, img_path)
