"""Video generation via Magic Hour API (wan-2.2 model).

Rotates 4 API keys to build a 15-second video from 3x 5-second clips.
Falls back to next key on failure.
"""
import os
import subprocess
import time

import requests

MAGIC_HOUR_API_URL = "https://api.magichour.ai/v1/image-to-video"
MAGIC_HOUR_MODEL = os.getenv("MAGIC_HOUR_MODEL", "wan-2.2")
RESOLUTION = os.getenv("VIDEO_RESOLUTION", "480p")
ASPECT_RATIO = "9:16"
POLL_TIMEOUT = int(os.getenv("MAGIC_HOUR_POLL_TIMEOUT", "600"))  # 10 min
POLL_INTERVAL = 5


def _get_keys():
    """Collect all VIDEO_KEY_N env vars in order."""
    keys = []
    for i in range(1, 6):
        k = os.getenv(f"VIDEO_KEY_{i}", "").strip()
        if k:
            keys.append((i, k))
    return keys


def _submit_job(image_url, prompt, duration, api_key):
    """Submit one generation job. Returns job_id or None."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MAGIC_HOUR_MODEL,
        "assets": {"image_url": image_url},
        "end_seconds": duration,
        "resolution": RESOLUTION,
        "aspect_ratio": ASPECT_RATIO,
        "prompt": prompt,
    }
    try:
        r = requests.post(MAGIC_HOUR_API_URL, headers=headers, json=payload, timeout=30)
        if r.status_code in (200, 201):
            data = r.json()
            return data.get("id") or data.get("job_id")
        print(f"    Submit HTTP {r.status_code}: {r.text[:150]}")
    except Exception as exc:
        print(f"    Submit error: {str(exc)[:120]}")
    return None


def _poll_job(job_id, api_key):
    """Poll until complete. Returns video URL or None."""
    headers = {"Authorization": f"Bearer {api_key}"}
    start = time.time()
    while time.time() - start < POLL_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        try:
            r = requests.get(f"{MAGIC_HOUR_API_URL}/{job_id}", headers=headers, timeout=30)
            if r.status_code != 200:
                continue
            data = r.json()
            status = data.get("status", "").lower()
            if status in ("complete", "completed", "succeeded"):
                return data.get("url") or data.get("download_url")
            if status in ("error", "failed"):
                print(f"    Job failed: {data.get('error', 'unknown')}")
                return None
            progress = data.get("progress", 0)
            elapsed = int(time.time() - start)
            print(f"    Status: {status} ({progress}%) [{elapsed}s]")
        except Exception:
            continue
    print(f"    Poll timeout after {POLL_TIMEOUT}s")
    return None


def _download(url, out_path):
    """Download video file."""
    try:
        r = requests.get(url, timeout=300, stream=True)
        if r.status_code == 200:
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
    except Exception as exc:
        print(f"    Download error: {str(exc)[:120]}")
    return False


def generate_clip(image_url, prompt, duration, out_path, key_index=None):
    """Generate ONE clip. If key_index given, use that key only.
    Otherwise rotate through all keys until success.
    """
    keys = _get_keys()
    if not keys:
        print("  No VIDEO_KEY_* found")
        return False

    # If specific key requested
    if key_index is not None:
        keys = [(i, k) for i, k in keys if i == key_index]

    for i, key in keys:
        print(f"  Trying VIDEO_KEY_{i}...")
        job_id = _submit_job(image_url, prompt, duration, key)
        if not job_id:
            continue
        video_url = _poll_job(job_id, key)
        if not video_url:
            continue
        if _download(video_url, out_path):
            print(f"  Clip OK via KEY_{i}: {out_path}")
            return True
    print("  All keys failed for this clip")
    return False


def generate_15s_video(image_url, prompt, out_path):
    """Build a 15-second video from 3x 5-second clips.

    Uses different keys for each clip to spread credit usage.
    Keys rotate: clip 1 -> key 1, clip 2 -> key 2, clip 3 -> key 3.
    If a key fails, the next key is tried automatically.
    """
    keys = _get_keys()
    if not keys:
        print("  No VIDEO_KEY_* found")
        return False

    print(f"  Found {len(keys)} keys")

    # 3 clips of 5 seconds each
    clip_paths = []
    for clip_idx in range(3):
        clip_path = out_path.replace(".mp4", f"_clip{clip_idx}.mp4")
        # Rotate key: clip 0 -> key 1, clip 1 -> key 2, clip 2 -> key 3
        # If only 4 keys, key 4 goes back to clip 0 on retry
        key_idx = (clip_idx % len(keys)) + 1

        # Try the assigned key first, then fall back to others
        print(f"  === Clip {clip_idx + 1}/3 ===")
        success = False

        # Try assigned key first
        assigned = [(i, k) for i, k in keys if i == key_idx]
        others = [(i, k) for i, k in keys if i != key_idx]

        for i, key in assigned + others:
            job_id = _submit_job(image_url, prompt, 5, key)
            if not job_id:
                continue
            video_url = _poll_job(job_id, key)
            if not video_url:
                continue
            if _download(video_url, clip_path):
                clip_paths.append(clip_path)
                success = True
                print(f"  Clip {clip_idx + 1} OK via KEY_{i}")
                break

        if not success:
            print(f"  Clip {clip_idx + 1} FAILED completely")

    if len(clip_paths) < 2:
        print(f"  Only {len(clip_paths)} clips succeeded - need at least 2")
        return False

    # Concatenate clips
    print(f"  Concatenating {len(clip_paths)} clips...")
    lst_path = out_path.replace(".mp4", "_list.txt")
    with open(lst_path, "w") as f:
        for cp in clip_paths:
            f.write(f"file '{os.path.abspath(cp)}'\n")

    try:
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", lst_path,
            "-c", "copy", "-movflags", "+faststart", out_path,
        ], check=True, timeout=180)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            print(f"  Final video: {out_path}")
            return True
    except Exception as exc:
        print(f"  Concat failed: {str(exc)[:200]}")
    return False


def pollinations_image(prompt, out_path, seed=None):
    """Base image for Magic Hour input (free Pollinations)."""
    import urllib.parse
    clean = " ".join(prompt.split())[:1200]
    encoded = urllib.parse.quote(clean)
    if seed is None:
        seed = int(time.time())
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=720&height=1280&model=flux"
        f"&nologo=true&enhance=true&safe=true&seed={seed}"
    )
    for attempt in range(1, 4):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and r.content and len(r.content) > 5000:
                with open(out_path, "wb") as f:
                    f.write(r.content)
                return True
            print(f"    Image HTTP {r.status_code}")
        except Exception as exc:
            print(f"    Image error: {str(exc)[:100]}")
        time.sleep(3)
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
            "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,"
                   "pad=720:1280:(ow-iw)/2:(oh-ih)/2",
            out_path,
        ], check=True, timeout=300)
        return True
    except Exception as exc:
        print(f"  Static video failed: {str(exc)[:150]}")
        return False
