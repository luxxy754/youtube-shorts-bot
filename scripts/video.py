"""Video generation for the YouTube Shorts bot.

Uses only Agnes AI (free, no credit card, indefinite free tier).
Multiple API keys rotate automatically to handle RPM limits.
"""

import os
import time
from urllib.parse import quote

import requests


CLIP_SECONDS = int(os.getenv("CLIP_SECONDS", "5"))

AGNES_MODEL = os.getenv("AGNES_MODEL", "agnes-video-2.5-flash")
AGNES_BASE = "https://apihub.agnes-ai.com/v1"


def _agnes_keys():
    """Collect all Agnes API keys from env, in order."""
    keys = []
    for i in range(1, 6):  # supports up to 5 keys
        k = os.getenv(f"AGNES_API_KEY_{i}", "").strip()
        if k:
            keys.append(k)
    # Backwards compatibility with the old single key name
    single = os.getenv("AGNES_API_KEY", "").strip()
    if single and single not in keys:
        keys.append(single)
    return keys


def agnes_video(prompt, path):
    """Agnes AI free text-to-video. Rotates through all available keys.

    Returns True on success, False if every key fails.
    """
    keys = _agnes_keys()
    if not keys:
        print("  No Agnes API key found (AGNES_API_KEY_1..N)")
        return False

    for idx, key in enumerate(keys, start=1):
        try:
            print(f"  Agnes (key {idx}/{len(keys)}) creating task...")

            create = requests.post(
                f"{AGNES_BASE}/videos",
                headers={
                    "Authorization": f"Bearer {key}",
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
                timeout=60,
            )

            if create.status_code != 200:
                msg = create.text[:200]
                print(f"  Agnes key {idx} create failed HTTP {create.status_code}: {msg}")
                continue

            data = create.json()
            video_id = data.get("video_id") or data.get("id") or data.get("task_id")
            if not video_id:
                print(f"  Agnes key {idx}: no video_id in response: {data}")
                continue

            print(f"  Agnes key {idx} task: {video_id}")

            # Poll for completion (max 10 minutes)
            max_wait = 600
            start = time.time()
            failed = False

            while time.time() - start < max_wait:
                time.sleep(5)

                poll = requests.get(
                    "https://apihub.agnes-ai.com/agnesapi",
                    params={"video_id": video_id, "model_name": AGNES_MODEL},
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=30,
                )

                if poll.status_code != 200:
                    print(f"  Agnes poll HTTP {poll.status_code}, retrying...")
                    continue

                result = poll.json()
                status = result.get("status")

                if status == "completed":
                    video_url = (result.get("metadata") or {}).get("url") or result.get("video_url")
                    if not video_url:
                        print(f"  Agnes key {idx} completed but no URL: {result}")
                        failed = True
                        break

                    print(f"  Agnes key {idx} completed, downloading...")
                    video_data = requests.get(video_url, timeout=300)
                    with open(path, "wb") as f:
                        f.write(video_data.content)
                    print(f"  Agnes key {idx} success")
                    return True

                if status == "failed":
                    print(f"  Agnes key {idx} failed: {result.get('error', 'unknown')}")
                    failed = True
                    break

                progress = result.get("progress", 0)
                print(f"  Agnes status: {status} ({progress}%)")

            if failed:
                continue

            print(f"  Agnes key {idx} timed out")

        except Exception as exc:
            print(f"  Agnes key {idx} error: {str(exc)[:200]}")
            continue

    print("  All Agnes keys failed.")
    return False


def make_clip(prompt, path, seed=0):
    """Generate one clip. Only Agnes AI is used."""
    print(f"Generating clip: {path}")

    if agnes_video(prompt, path):
        print("  Clip generated with Agnes AI.")
        return True

    print("  Agnes unavailable, clip skipped.")
    return False
