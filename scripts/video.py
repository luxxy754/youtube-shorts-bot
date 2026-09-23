"""Image generation for cat animation frames - PARALLEL version.

Uses ThreadPoolExecutor to fetch multiple images concurrently.
Pollinations handles concurrent requests well; 8 parallel = 5-10x faster.
"""
import os
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

IMAGE_WIDTH = 1080
IMAGE_HEIGHT = 1920
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "flux")
IMAGE_TIMEOUT = int(os.getenv("IMAGE_TIMEOUT", "90"))
IMAGE_RETRIES = int(os.getenv("IMAGE_RETRIES", "2"))
IMAGE_CONCURRENCY = int(os.getenv("IMAGE_CONCURRENCY", "8"))

# Shared session = faster (connection reuse)
_session = requests.Session()
_session.headers.update({"User-Agent": "cat-shorts-bot/1.0"})


def _download_image(prompt: str, out_path: str, seed: int):
    """Fetch one image. Returns (out_path, success)."""
    clean = " ".join(prompt.split())[:1200]
    encoded = urllib.parse.quote(clean)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={IMAGE_WIDTH}&height={IMAGE_HEIGHT}"
        f"&model={IMAGE_MODEL}"
        f"&nologo=true&enhance=true&safe=true"
        f"&seed={seed}"
    )
    for attempt in range(1, IMAGE_RETRIES + 1):
        try:
            r = _session.get(url, timeout=IMAGE_TIMEOUT)
            if r.status_code == 200 and r.content and len(r.content) > 5000:
                with open(out_path, "wb") as f:
                    f.write(r.content)
                return (out_path, True)
        except Exception as exc:
            print(f"    Image err ({os.path.basename(out_path)}): {str(exc)[:80]}")
        if attempt < IMAGE_RETRIES:
            time.sleep(2)
    return (out_path, False)


def generate_scene_frames(prompt_fn, scene_index, n_frames, out_dir, base_seed=0):
    """Generate N frames for ONE scene in parallel."""
    print(f"  Generating {n_frames} frames in parallel (scene {scene_index + 1})...")

    tasks = []
    for f in range(n_frames):
        fp = os.path.join(out_dir, f"scene_{scene_index}_frame_{f}.jpg")
        seed = base_seed + scene_index * 1000 + f
        tasks.append((prompt_fn(f), fp, seed))

    results = {}
    with ThreadPoolExecutor(max_workers=IMAGE_CONCURRENCY) as pool:
        futures = {
            pool.submit(_download_image, prompt, fp, seed): (f_idx, fp)
            for f_idx, (prompt, fp, seed) in enumerate(tasks)
        }
        for fut in as_completed(futures):
            f_idx, fp = futures[fut]
            try:
                _, ok = fut.result()
                results[f_idx] = ok
                status = "OK" if ok else "FAIL"
                print(f"    Frame {f_idx + 1}/{n_frames}: {status}")
            except Exception as exc:
                results[f_idx] = False
                print(f"    Frame {f_idx + 1}/{n_frames}: ERR {str(exc)[:80]}")

    # Build list of frame paths (with fallback repetition)
    frames = []
    for f in range(n_frames):
        fp = os.path.join(out_dir, f"scene_{scene_index}_frame_{f}.jpg")
        if results.get(f) and os.path.exists(fp):
            frames.append(fp)
        elif frames:
            frames.append(frames[-1])   # repeat previous frame
        else:
            # No frames yet - keep trying to find any
            pass

    return frames


def generate_all_frames(all_tasks, out_dir):
    """Generate ALL scenes' frames in one giant parallel batch.

    all_tasks = list of (scene_index, frame_index, prompt, out_path, seed)
    Returns dict: {(scene_index, frame_index): bool}
    """
    print(f"  Generating {len(all_tasks)} images total (parallel)...")

    results = {}
    with ThreadPoolExecutor(max_workers=IMAGE_CONCURRENCY) as pool:
        futures = {}
        for (si, fi, prompt, fp, seed) in all_tasks:
            fut = pool.submit(_download_image, prompt, fp, seed)
            futures[fut] = (si, fi, fp)

        done = 0
        total = len(futures)
        for fut in as_completed(futures):
            si, fi, fp = futures[fut]
            try:
                _, ok = fut.result()
                results[(si, fi)] = ok
            except Exception:
                results[(si, fi)] = False
            done += 1
            if done % 4 == 0 or done == total:
                print(f"    Progress: {done}/{total}")

    return results
