"""Video generation for the YouTube Shorts bot.

Uses only Agnes AI (free, no credit card).
Multi-key rotation + retry on 503 (queue full) and 429 (rate limit).
"""

import os
import time

import requests


CLIP_SECONDS = int(os.getenv("CLIP_SECONDS", "5"))

AGNES_MODEL = os.getenv("AGNES_MODEL", "agnes-video-2.5-flash")
AGNES_BASE = "https://apihub.agnes-ai.com/v1"


def _agnes_keys():
    """Collect all Agnes API keys from env, in order."""
    keys = []
    for i in range(1, 6):
        k = os.getenv(f"AGNES_API_KEY_{i}", "").strip()
        if k:
            keys.append(k)
    single = os.getenv("AGNES_API_KEY", "").strip()
    if single and single not in keys:
        keys.append(single)
    return keys


def agnes_video(prompt, path):
    """Agnes AI free text-to-video. Rotates keys + retries on 503/429."""
    keys = _agnes_keys()
    if not keys:
        print("  No Agnes API key found (AGNES_API_KEY_1..N)")
        return False

    # 3 rounds of trying all keys — handles queue full / rate limit
    for round_num in range(1, 4):
        for idx, key in enumerate(keys, start=1):
            try:
                print(f"  Agnes round {round_num}, key {idx}/{len(keys)} creating task...")

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

                # Queue full or rate limit -> try next key / next round
                if create.status_code in (429, 503):
                    print(f"  Agnes key {idx} busy ({create.status_code}), will retry...")
                    continue

                if create.status_code != 200:
                    print(f"  Agnes key {idx} create failed HTTP {create.status_code}: {create.text[:200]}")
                    continue

                data = create.json()
                video_id = data.get("video_id") or data.get("id") or data.get("task_id")
                if not video_id:
                    print(f"  Agnes key {idx}: no video_id: {data}")
                    continue

                print(f"  Agnes key {idx} task: {video_id}")

                # Poll for completion
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
                        continue

                    result = poll.json()
                    status = result.get("status")

                    if status == "completed":
                        video_url = (result.get("metadata") or {}).get("url") or result.get("video_url")
                        if not video_url:
                            failed = True
                            break
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

            except Exception as exc:
                print(f"  Agnes key {idx} error: {str(exc)[:200]}")
                continue

        # Round finished — wait 60s before next round
        if round_num < 3:
            print(f"  Round {round_num} done, waiting 60s before retry...")
            time.sleep(60)

    print("  All Agnes keys failed after 3 rounds.")
    return False


def make_clip(prompt, path, seed=0):
    """Generate one clip. Only Agnes AI is used."""
    print(f"Generating clip: {path}")

    if agnes_video(prompt, path):
        print("  Clip generated with Agnes AI.")
        return True

    print("  Agnes unavailable, clip skipped.")
    return False
