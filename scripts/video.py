"""Video generation via Magic Hour API - CORRECT flow.

Step 1: Get upload URL from Magic Hour
Step 2: PUT image to that URL -> get file_path
Step 3: Submit video job with assets.image_file_path
"""
import os
import subprocess
import time

import requests

MH_BASE = "https://api.magichour.ai/v1"
MH_UPLOAD_URLS = f"{MH_BASE}/files/upload-urls"
MH_VIDEO_URL = f"{MH_BASE}/image-to-video"
MH_MODEL = os.getenv("MAGIC_HOUR_MODEL", "wan-2.2")
RESOLUTION = os.getenv("VIDEO_RESOLUTION", "480p")
ASPECT_RATIO = "9:16"
POLL_TIMEOUT = int(os.getenv("MAGIC_HOUR_POLL_TIMEOUT", "900"))
POLL_INTERVAL = 5


def _get_keys():
    keys = []
    for i in range(1, 6):
        k = os.getenv(f"VIDEO_KEY_{i}", "").strip()
        if k:
            keys.append((i, k))
    return keys


def _get_upload_url(api_key, filename):
    """Step 1: Ask Magic Hour for an upload URL."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"files": [{"filename": filename, "content_type": "image/jpeg"}]}
    r = requests.post(MH_UPLOAD_URLS, headers=headers, json=payload, timeout=60)
    print(f"    Upload-URLs HTTP {r.status_code}")
    if r.status_code not in (200, 201):
        print(f"    Body: {r.text[:250]}")
        return None, None

    data = r.json()
    # Response shape possibilities:
    # {"uploads": [{"upload_url": "...", "file_path": "..."}]}
    # {"files": [{"url": "...", "path": "..."}]}
    # {"upload_url": "...", "file_path": "..."}
    uploads = data.get("uploads") or data.get("files") or [data]
    if not uploads:
        print(f"    No upload entries: {data}")
        return None, None

    first = uploads[0]
    upload_url = (
        first.get("upload_url")
        or first.get("url")
        or first.get("signed_url")
    )
    file_path = (
        first.get("file_path")
        or first.get("path")
        or first.get("id")
    )
    if not upload_url or not file_path:
        print(f"    Missing fields: {first}")
        return None, None
    print(f"    Upload URL OK, file_path: {file_path}")
    return upload_url, file_path


def _put_to_upload_url(upload_url, image_path):
    """Step 2: PUT the image to the signed upload URL."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    r = requests.put(
        upload_url,
        data=image_bytes,
        headers={"Content-Type": "image/jpeg"},
        timeout=120,
    )
    print(f"    PUT HTTP {r.status_code}")
    return r.status_code in (200, 201, 204)


def _submit_job(image_file_path, prompt, duration, api_key):
    """Step 3: Submit video job with file_path."""
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
    r = requests.post(MH_VIDEO_URL, headers=headers, json=payload, timeout=30)
    print(f"    Submit HTTP {r.status_code}")
    if r.status_code in (200, 201):
        data = r.json()
        job_id = data.get("id") or data.get("job_id")
        print(f"    Job ID: {job_id}")
        return job_id
    print(f"    Body: {r.text[:250]}")
    return None


def _poll_job(job_id, api_key):
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
    print(f"    Poll timeout")
    return None


def _download(url, out_path):
    r = requests.get(url, timeout=300, stream=True)
    if r.status_code == 200:
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return True
    print(f"    Download HTTP {r.status_code}")
    return False


def generate_clip(image_path, prompt, duration, out_path, api_key):
    """Full flow: upload -> submit -> poll -> download."""
    filename = os.path.basename(image_path)

    # Step 1: Get upload URL
    upload_url, file_path = _get_upload_url(api_key, filename)
    if not upload_url:
        return False

    # Step 2: Upload image
    if not _put_to_upload_url(upload_url, image_path):
        print("    Image PUT failed")
        return False

    # Step 3: Submit video job
    job_id = _submit_job(file_path, prompt, duration, api_key)
    if not job_id:
        return False

    # Step 4: Poll
    video_url = _poll_job(job_id, api_key)
    if not video_url:
        return False

    # Step 5: Download
    return _download(video_url, out_path)


def generate_15s_video(image_path, prompt, out_path):
    """Build 15s video from 3x 5s clips using 4 keys."""
    keys = _get_keys()
    if not keys:
        print("  No VIDEO_KEY_* found")
        return False
    print(f"  Found {len(keys)} keys")

    clip_paths = []
    for clip_idx in range(3):
        clip_path = out_path.replace(".mp4", f"_clip{clip_idx}.mp4")
        key_idx = (clip_idx % len(keys)) + 1
        print(f"  === Clip {clip_idx + 1}/3 (KEY_{key_idx}) ===")

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
        print(f"  Only {len(clip_paths)} clips - need 2+")
        return False

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
            print(f"  Final: {out_path}")
            return True
    except Exception as exc:
        print(f"  Concat err: {str(exc)[:150]}")
    return False


def pollinations_image(prompt, out_path, seed=None):
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
            print(f"    Image err: {str(exc)[:100]}")
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
    except Exception as exc:
        print(f"  Static failed: {str(exc)[:200]}")
        return False
