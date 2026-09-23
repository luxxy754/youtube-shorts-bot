"""Video generation via Magic Hour API (wan-2.2 model) using image_url."""
import os
import subprocess
import time

import requests

MH_VIDEO_URL = "https://api.magichour.ai/v1/image-to-video"
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


def _upload_public(image_path):
    """Upload image to a public host and return direct URL."""
    # Try 1: catbox.moe
    try:
        print("    Trying catbox.moe...")
        with open(image_path, "rb") as f:
            r = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": f},
                timeout=90,
            )
        if r.status_code == 200 and r.text.strip().startswith("http"):
            url = r.text.strip()
            print(f"    catbox.moe OK: {url}")
            return url
        print(f"    catbox.moe HTTP {r.status_code}")
    except Exception as exc:
        print(f"    catbox.moe err: {str(exc)[:100]}")

    # Try 2: tmpfiles.org
    try:
        print("    Trying tmpfiles.org...")
        with open(image_path, "rb") as f:
            r = requests.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": f},
                timeout=90,
            )
        if r.status_code == 200:
            data = r.json()
            url = data.get("data", {}).get("url", "")
            if url:
                direct = url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                print(f"    tmpfiles.org OK: {direct}")
                return direct
        print(f"    tmpfiles.org HTTP {r.status_code}")
    except Exception as exc:
        print(f"    tmpfiles.org err: {str(exc)[:100]}")

    # Try 3: uguu.se
    try:
        print("    Trying uguu.se...")
        with open(image_path, "rb") as f:
            r = requests.post(
                "https://uguu.se/upload.php",
                files={"files[]": f},
                timeout=90,
            )
        if r.status_code == 200:
            files = r.json().get("files", [])
            if files and files[0].get("url"):
                url = files[0]["url"]
                print(f"    uguu.se OK: {url}")
                return url
        print(f"    uguu.se HTTP {r.status_code}")
    except Exception as exc:
        print(f"    uguu.se err: {str(exc)[:100]}")

    print("    All upload hosts failed")
    return None


def _submit_job(image_url, prompt, duration, api_key):
    """Submit video job using image_url (CORRECT field name)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MH_MODEL,
        "assets": {"image_url": image_url},  # <-- Correct field!
        "end_seconds": duration,
        "resolution": RESOLUTION,
        "aspect_ratio": ASPECT_RATIO,
        "prompt": prompt,
    }
    try:
        r = requests.post(MH_VIDEO_URL, headers=headers, json=payload, timeout=30)
        print(f"    Submit HTTP {r.status_code}")
        if r.status_code in (200, 201):
            data = r.json()
            job_id = data.get("id") or data.get("job_id")
            print(f"    Job ID: {job_id}")
            return job_id
        print(f"    Body: {r.text[:250]}")
    except Exception as exc:
        print(f"    Submit err: {str(exc)[:150]}")
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
    print(f"    Poll timeout after {POLL_TIMEOUT}s")
    return None


def _download(url, out_path):
    try:
        r = requests.get(url, timeout=300, stream=True)
        if r.status_code == 200:
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
        print(f"    Download HTTP {r.status_code}")
    except Exception as exc:
        print(f"    Download err: {str(exc)[:120]}")
    return False


def generate_clip(image_url, prompt, duration, out_path, api_key):
    job_id = _submit_job(image_url, prompt, duration, api_key)
    if not job_id:
        return False
    video_url = _poll_job(job_id, api_key)
    if not video_url:
        return False
    return _download(video_url, out_path)


def generate_15s_video(image_path, prompt, out_path):
    """Build 15-second video from 3x 5-second clips."""
    keys = _get_keys()
    if not keys:
        print("  No VIDEO_KEY_* found")
        return False
    print(f"  Found {len(keys)} keys")

    # Upload image ONCE
    print("  Uploading image to public host...")
    image_url = _upload_public(image_path)
    if not image_url:
        print("  Public URL failed")
        return False

    clip_paths = []
    for clip_idx in range(3):
        clip_path = out_path.replace(".mp4", f"_clip{clip_idx}.mp4")
        key_idx = (clip_idx % len(keys)) + 1
        print(f"  === Clip {clip_idx + 1}/3 (KEY_{key_idx}) ===")

        ordered = [(i, k) for i, k in keys if i == key_idx] + \
                  [(i, k) for i, k in keys if i != key_idx]

        success = False
        for i, key in ordered:
            if generate_clip(image_url, prompt, 5, clip_path, key):
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
