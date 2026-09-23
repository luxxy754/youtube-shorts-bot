"""Image generation for cat animation + Wav2Lip lipsync."""
import os
import subprocess
import time
import urllib.parse

import requests

IMAGE_WIDTH = 1080
IMAGE_HEIGHT = 1920
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "flux")
IMAGE_TIMEOUT = int(os.getenv("IMAGE_TIMEOUT", "240"))
IMAGE_RETRIES = int(os.getenv("IMAGE_RETRIES", "3"))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAV2LIP_DIR = os.path.join(ROOT, "Wav2Lip")
WAV2LIP_CHECKPOINT = os.getenv(
    "WAV2LIP_CHECKPOINT",
    os.path.join(WAV2LIP_DIR, "checkpoints", "wav2lip_gan.pth"),
)


def pollinations_image(prompt: str, out_path: str, seed: int = None) -> bool:
    """Generate one image. Seed helps consistency."""
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
    """Generate N frames for one scene.

    prompt_fn(frame_index) -> prompt string
    Returns list of frame paths (only successful ones).
    """
    frames = []
    for f in range(n_frames):
        fp = os.path.join(out_dir, f"scene_{scene_index}_frame_{f}.jpg")
        # Same seed + offset ensures similar character across frames
        seed = base_seed + scene_index * 1000 + f
        if pollinations_image(prompt_fn(f), fp, seed=seed):
            frames.append(fp)
            print(f"  Frame {f+1}/{n_frames} OK")
        else:
            print(f"  Frame {f+1}/{n_frames} FAILED - using previous")
            if frames:
                frames.append(frames[-1])  # repeat last frame
    return frames


def wav2lip_sync(image_path, audio_path, out_path):
    """Run Wav2Lip on a single image."""
    if not os.path.exists(WAV2LIP_CHECKPOINT):
        print(f"  Wav2Lip checkpoint missing")
        return False
    inference_script = os.path.join(WAV2LIP_DIR, "inference.py")
    if not os.path.exists(inference_script):
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
            print(f"  Wav2Lip fail: {result.stderr[-300:]}")
            return False
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            print(f"  Wav2Lip OK")
            return True
        return False
    except Exception as exc:
        print(f"  Wav2Lip err: {str(exc)[:200]}")
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
            "-t", dur, "-shortest",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
                   "pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            out_path,
        ], check=True, timeout=300)
        return True
    except Exception as exc:
        print(f"  Static fail: {str(exc)[:200]}")
        return False
