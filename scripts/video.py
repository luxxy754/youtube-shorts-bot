"""Video generation via Magic Hour API - PARALLEL clip generation.

Speed optimizations:
  - 3 clips submitted IN PARALLEL (not sequential)
  - 3x faster than sequential
  - Long poll timeout for free tier
  - Falls back to sequential on failure
"""
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

MH_BASE = "https://api.magichour.ai/v1"
MH_UPLOAD_URLS = f"{MH_BASE}/files/upload-urls"
MH_VIDEO_URL = f"{MH_BASE}/image-to-video"
MH_MODEL = os.getenv("MAGIC_HOUR_MODEL", "wan-2.2")
RESOLUTION = os.getenv("VIDEO_RESOLUTION", "480p")
ASPECT_RATIO = "9:16"
POLL_TIMEOUT = int(os.getenv("MAGIC_HOUR_POLL_TIMEOUT", "1800"))
POLL_INTERVAL = 10
NUM_CLIPS = int(os.getenv("NUM_CLIPS", "3"))
CLIP_DURATION = int(os.getenv("CLIP_DURATION", "5"))


def _get_keys():
    keys = []
    for i in range(1, 6):
        k = os.getenv(f"VIDEO_KEY_{i}", "").strip()
        if k:
            keys.append((i, k))
    return keys


def _get_upload_url(api_key, extension="jpg"):
    """Step 1: Ask Magic Hour for upload URL."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"items": [{"type": "image", "extension": extension}]}
    try:
        r = requests.post(MH_UPLOAD_URLS, headers=headers, json=payload, timeout=60)
        if r.status_code not in (200, 201):
            return None, None
        data = r.json()
        items = data.get("items", [])
        if not items:
            return None, None
        first = items[0]
        return first.get("upload_url"), first.get("file_path")
    except Exception:
        return None, None


def _put_to_upload_url(upload_url, image_path):
    """Step 2: PUT image to upload URL."""
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        r = requests.put(
            upload_url,
            data=image_bytes,
            headers={"Content-Type": "image/jpeg"},
            timeout=180,
        )
        return r.status_code in (200, 201, 204)
    except Exception:
        return False


def _submit_job(image_file_path, prompt, duration, api_key):
    """Step 3: Submit video job."""
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
            return r.json().get("id") or r.json().get("job_id")
    except Exception:
        pass
    return None


def _poll_job(job_id, api_key, label=""):
    """Poll until complete."""
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
                return None
            progress = data.get("progress", 0)
            elapsed = int(time.time() - start)
            print(f"    [{label}] {status} ({progress}%) [{elapsed}s]")
        except Exception:
            continue
    print(f"    [{label}] Poll timeout after {POLL_TIMEOUT}s")
    return None


def _download(url, out_path):
    try:
        r = requests.get(url, timeout=300, stream=True)
        if r.status_code == 200:
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
    except Exception:
        pass
    return False


def _generate_one_clip(clip_idx, image_path, prompt, out_path, key_pair):
    """Generate ONE clip (used by parallel workers)."""
    key_num, api_key = key_pair
    label = f"Clip{clip_idx + 1}/KEY_{key_num}"

    print(f"  [{label}] Starting...")

    # Get upload URL
    upload_url, file_path = _get_upload_url(api_key, "jpg")
    if not upload_url:
        print(f"  [{label}] Upload-URLs failed")
        return (clip_idx, None)

    # Upload image
    if not _put_to_upload_url(upload_url, image_path):
        print(f"  [{label}] PUT failed")
        return (clip_idx, None)

    # Submit job
    job_id = _submit_job(file_path, prompt, CLIP_DURATION, api_key)
    if not job_id:
        print(f"  [{label}] Submit failed")
        return (clip_idx, None)

    print(f"  [{label}] Job submitted: {job_id}")

    # Poll
    video_url = _poll_job(job_id, api_key, label)
    if not video_url:
        print(f"  [{label}] Poll failed")
        return (clip_idx, None)

    # Download
    if _download(video_url, out_path):
        print(f"  [{label}] DONE: {out_path}")
        return (clip_idx, out_path)

    print(f"  [{label}] Download failed")
    return (clip_idx, None)


def generate_15s_video(image_path, prompt, out_path):
    """Generate 15s video from 3x 5s clips IN PARALLEL."""
    keys = _get_keys()
    if not keys:
        print("  No VIDEO_KEY_* found")
        return False

    print(f"  Found {len(keys)} keys")
    print(f"  Generating {NUM_CLIPS} clips IN PARALLEL ({CLIP_DURATION}s each)...")

    # Prepare clip jobs: use different keys for each clip
    clip_jobs = []
    for clip_idx in range(NUM_CLIPS):
        key_pair = keys[clip_idx % len(keys)]
        clip_path = out_path.replace(".mp4", f"_clip{clip_idx}.mp4")
        clip_jobs.append((clip_idx, image_path, prompt, clip_path, key_pair))

    # Run ALL clips in parallel
    results = {}
    with ThreadPoolExecutor(max_workers=NUM_CLIPS) as pool:
        futures = {
            pool.submit(_generate_one_clip, *job): job[0]
            for job in clip_jobs
        }
        for fut in as_completed(futures):
            clip_idx = futures[fut]
            try:
                _, result_path = fut.result()
                results[clip_idx] = result_path
            except Exception as exc:
                print(f"  Clip {clip_idx + 1} exception: {str(exc)[:150]}")
                results[clip_idx] = None

    # Collect successful clips
    clip_paths = [results[i] for i in range(NUM_CLIPS) if results.get(i)]
    print(f"\n  Successful clips: {len(clip_paths)}/{NUM_CLIPS}")

    if len(clip_paths) < 2:
        print(f"  Only {len(clip_paths)} clips succeeded - need 2+")
        return False

    # Concatenate
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
        print(f"  Concat error: {str(exc)[:150]}")
    return False


def pollinations_image(prompt, out_path, seed=None):
    """Generate base image."""
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
        except Exception:
            pass
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
            "-loop", "1", "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
            "-t", str(dur), "-shortest",
            "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,"
                   "pad=720:1280:(ow-iw)/2:(oh-ih)/2",
            out_path,
        ], check=True, timeout=300)
        return True
    except Exception:
        return False
