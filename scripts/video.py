"""Video generation via Agnes AI - CORRECT model for video."""
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

AGNES_BASE = "https://apihub.agnes-ai.com/v1"
AGNES_MODEL = os.getenv("AGNES_MODEL", "agnes-video-2.5")
CLIP_SECONDS = int(os.getenv("CLIP_SECONDS", "5"))
NUM_CLIPS = int(os.getenv("NUM_CLIPS", "3"))
POLL_TIMEOUT = int(os.getenv("AGNES_POLL_TIMEOUT", "600"))
POLL_INTERVAL = int(os.getenv("AGNES_POLL_INTERVAL", "3"))


def _get_keys():
    keys = []
    for i in range(1, 6):
        k = os.getenv(f"AGNES_API_KEY_{i}", "").strip()
        if not k and i == 1:
            k = os.getenv("AGNES_API_KEY", "").strip()
        if k:
            keys.append((i, k))
    return keys


def _create_task(prompt, api_key):
    """Create a video generation task."""
    try:
        r = requests.post(
            f"{AGNES_BASE}/videos",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": AGNES_MODEL,
                "prompt": prompt,
                "mode": "text",
                "seconds": str(CLIP_SECONDS),
                "size": "720P",
                "aspect_ratio": "9:16",
            },
            timeout=30,
        )
        print(f"    Create HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            return data.get("video_id") or data.get("id") or data.get("task_id")
        print(f"    Body: {r.text[:300]}")
    except Exception as exc:
        print(f"    Create err: {str(exc)[:150]}")
    return None


def _poll_task(task_id, api_key, label=""):
    """Poll until complete."""
    start = time.time()
    while time.time() - start < POLL_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        try:
            r = requests.get(
                "https://apihub.agnes-ai.com/agnesapi",
                params={"video_id": task_id, "model_name": AGNES_MODEL},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=20,
            )
            if r.status_code != 200:
                continue
            data = r.json()
            status = (data.get("status") or "").lower()

            if status == "completed":
                url = (data.get("metadata") or {}).get("url") or data.get("video_url")
                return url
            if status in ("failed", "error"):
                print(f"    [{label}] Failed: {data.get('error', 'unknown')}")
                return None

            progress = data.get("progress", 0)
            elapsed = int(time.time() - start)
            print(f"    [{label}] {status} ({progress}%) [{elapsed}s]")
        except Exception:
            continue
    print(f"    [{label}] Poll timeout")
    return None


def _download(url, out_path):
    try:
        r = requests.get(url, timeout=180, stream=True)
        if r.status_code == 200:
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
    except Exception:
        pass
    return False


def _generate_one_clip(clip_idx, prompt, out_path, key_pair):
    key_num, api_key = key_pair
    label = f"Clip{clip_idx + 1}/K{key_num}"

    print(f"  [{label}] Creating task...")
    task_id = _create_task(prompt, api_key)
    if not task_id:
        print(f"  [{label}] Task creation failed")
        return (clip_idx, None)

    print(f"  [{label}] Task: {task_id}")
    video_url = _poll_task(task_id, api_key, label)
    if not video_url:
        return (clip_idx, None)

    if _download(video_url, out_path):
        print(f"  [{label}] DONE")
        return (clip_idx, out_path)
    return (clip_idx, None)


def generate_15s_video(image_path, prompt, out_path):
    keys = _get_keys()
    if not keys:
        print("  No AGNES_API_KEY_* found")
        return False

    print(f"  Found {len(keys)} Agnes keys")
    print(f"  Generating {NUM_CLIPS} clips IN PARALLEL ({CLIP_SECONDS}s each)...")

    clip_jobs = []
    for clip_idx in range(NUM_CLIPS):
        key_pair = keys[clip_idx % len(keys)]
        clip_path = out_path.replace(".mp4", f"_clip{clip_idx}.mp4")
        clip_jobs.append((clip_idx, prompt, clip_path, key_pair))

    results = {}
    with ThreadPoolExecutor(max_workers=NUM_CLIPS) as pool:
        futures = {pool.submit(_generate_one_clip, *job): job[0] for job in clip_jobs}
        for fut in as_completed(futures):
            clip_idx = futures[fut]
            try:
                _, path = fut.result()
                results[clip_idx] = path
            except Exception:
                results[clip_idx] = None

    clip_paths = [results[i] for i in range(NUM_CLIPS) if results.get(i)]
    print(f"\n  Successful: {len(clip_paths)}/{NUM_CLIPS}")

    if len(clip_paths) < 2:
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
        ], check=True, timeout=120)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 10000
    except Exception:
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
            r = requests.get(url, timeout=90)
            if r.status_code == 200 and r.content and len(r.content) > 5000:
                with open(out_path, "wb") as f:
                    f.write(r.content)
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def static_video(image_path, audio_path, out_path):
    """Fallback: static image + audio (FIXED ffmpeg command)."""
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
        print(f"  Static err: {str(exc)[:200]}")
        return False
