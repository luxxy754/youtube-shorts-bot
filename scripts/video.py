"""Video generation via Magic Hour API (wan-2.2 model).

Two-step process:
  1. Upload image to Magic Hour -> get file_path
  2. Submit video job with file_path -> poll -> download
"""
import os
import subprocess
import time

import requests

# Magic Hour endpoints
MH_UPLOAD_URL = "https://api.magichour.ai/v1/files/upload"
MH_VIDEO_URL = "https://api.magichour.ai/v1/image-to-video"
MH_MODEL = os.getenv("MAGIC_HOUR_MODEL", "wan-2.2")
RESOLUTION = os.getenv("VIDEO_RESOLUTION", "480p")
ASPECT_RATIO = "9:16"
POLL_TIMEOUT = int(os.getenv("MAGIC_HOUR_POLL_TIMEOUT", "900"))
POLL_INTERVAL = 5


def _get_keys():
    """Collect all VIDEO_KEY_N env vars in order."""
    keys = []
    for i in range(1, 6):
        k = os.getenv(f"VIDEO_KEY_{i}", "").strip()
        if k:
            keys.append((i, k))
    return keys


def _upload_image_to_magichour(image_path, api_key):
    """Upload image to Magic Hour, get file_path (not URL).

    Returns the file_path string or None.
    """
    try:
        with open(image_path, "rb") as f:
            files = {"file": (os.path.basename(image_path), f, "image/jpeg")}
            headers = {"Authorization": f"Bearer {api_key}"}
            r = requests.post(
                MH_UPLOAD_URL,
                headers=headers,
                files=files,
                timeout=120,
            )
        if r.status_code in (200, 201):
            data = r.json()
            # Try multiple possible field names
            for field in ("file_path", "path", "id", "url", "file_url"):
                if data.get(field):
                    print(f"    Upload OK ({field}): {data[field]}")
                    return data[field]
            print(f"    Upload OK but no path field: {data}")
            return None
        print(f"    Upload HTTP {r.status_code}: {r.text[:200]}")
    except Exception as exc:
        print(f"    Upload error: {str(exc)[:150]}")
    return None


def _submit_job(image_file_path, prompt, duration, api_key):
    """Submit video generation job with file_path."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MH_MODEL,
        "assets": {"image_file_path": image_file_path},
        "end_seconds": duration,
        "resolution": RESOLUTION,
        "aspect_ratio": ASPECT_RATIO,
        "prompt": prompt,
    }
    try:
        r = requests.post(MH_VIDEO_URL, headers=headers, json=payload, timeout=30)
        if r.status_code in (200, 201):
            data = r.json()
            return data.get("id") or data.get("job_id")
        print(f"    Submit HTTP {r.status_code}: {r.text[:200]}")
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
            r = requests.get(f"{MH_VIDEO_URL}/{job_id}", headers=headers, timeout=30)
            if r.status_code != 200:
                continue
            data = r.json()
            status = data.get("status", "").lower()
            if status in ("complete", "completed", "succeeded", "done"):
                url = data.get("url") or data.get("download_url")
                if not url:
                    downloads = data.get("downloads", [])
                    if downloads and isinstance(downloads, list):
                        url = downloads[0].get("url")
                return url
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
    """Download video."""
    try:
        r = requests.get(url, timeout=300, stream=True)
        if r.status_code == 200:
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
        print(f"    Download HTTP {r.status_code}")
    except Exception as exc:
        print(f"    Download error: {str(exc)[:120]}")
    return False


def generate_clip(image_path, prompt, duration, out_path, api_key):
    """Generate ONE clip via Magic Hour:
       1. Upload image
       2. Submit video job
       3. Poll + download
    """
    # Step 1: Upload
    print(f"    [1/3] Uploading image...")
    file_path = _upload_image_to_magichour(image_path, api_key)
    if not file_path:
        return False

    # Step 2: Submit video job
    print(f"    [2/3] Submitting video job...")
    job_id = _submit_job(file_path, prompt, duration, api_key)
    if not job_id:
        return False

    # Step 3: Poll
    print(f"    [3/3] Generating ({duration}s)...")
    video_url = _poll_job(job_id, api_key)
    if not video_url:
        return False

    return _download(video_url, out_path)


def generate_15s_video(image_path, prompt, out_path):
    """Build 15-second video from 3x 5-second clips using 4 keys."""
    keys = _get_keys()
    if not keys:
        print("  No VIDEO_KEY_* found")
        return False

    print(f"  Found {len(keys)} keys")

    clip_paths = []
    for clip_idx in range(3):
        clip_path = out_path.replace(".mp4", f"_clip{clip_idx}.mp4")
        key_idx = (clip_idx % len(keys)) + 1

        print(f"  === Clip {clip_idx + 1}/3 (using KEY_{key_idx}) ===")

        # Try assigned key first, then rotate through others
        ordered = [(i, k) for i, k in keys if i == key_idx] + \
                  [(i, k) for i, k in keys if i != key_idx]

        success = False
        for i, key in ordered:
            if generate_clip(image_path, prompt, 5, clip_path, key):
                clip_paths.append(clip_path)
                success = True
                print(f"  Clip {clip_idx + 1} OK via KEY_{i}")
                break

        if not success:
            print(f"  Clip {clip_idx + 1} FAILED")

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
    """Generate base image (free)."""
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
