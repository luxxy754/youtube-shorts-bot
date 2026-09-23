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

# ---- Time budget knobs (tune these if you still hit the workflow timeout) ----
# Max seconds to wait for ONE clip to finish (was 600 - too long).
POLL_MAX_WAIT = int(os.getenv("AGNES_POLL_MAX_WAIT", "240"))   # 4 min per clip
# Seconds between status polls.
POLL_INTERVAL = int(os.getenv("AGNES_POLL_INTERVAL", "5"))
# Seconds to wait between retry rounds.
ROUND_WAIT = int(os.getenv("AGNES_ROUND_WAIT", "20"))
# Number of rounds (each round tries all keys once).
MAX_ROUNDS = int(os.getenv("AGNES_MAX_ROUNDS", "2"))


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
    """Agnes AI free text-to-video. Rotates keys + retries on 503/429.

    Total worst-case time budget per clip:
        MAX_ROUNDS * len(keys) * POLL_MAX_WAIT
    Keep this BELOW the workflow's step timeout in main.yml.
    """
    keys = _agnes_keys()
    if not keys:
        print("  No Agnes API key found (AGNES_API_KEY_1..N)")
        return False

    overall_start = time.time()
    overall_budget = MAX_ROUNDS * len(keys) * POLL_MAX_WAIT

    for round_num in range(1, MAX_ROUNDS + 1):
        for idx, key in enumerate(keys, start=1):
            if time.time() - overall_start > overall_budget:
                print("  Overall time budget exhausted, giving up on this clip.")
                return False

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

                # Queue full / rate limit -> try next key
                if create.status_code in (429, 503):
                    print(f"  Agnes key {idx} busy ({create.status_code}), trying next key...")
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

                start = time.time()
                failed = False

                while time.time() - start < POLL_MAX_WAIT:
                    time.sleep(POLL_INTERVAL)

                    try:
                        poll = requests.get(
                            "https://apihub.agnes-ai.com/agnesapi",
                            params={"video_id": video_id, "model_name": AGNES_MODEL},
                            headers={"Authorization": f"Bearer {key}"},
                            timeout=30,
                        )
                    except Exception as poll_exc:
                        print(f"  Poll error: {str(poll_exc)[:120]}")
                        continue

                    if poll.status_code != 200:
                        continue

                    result = poll.json()
                    status = result.get("status")

                    if status == "completed":
                        video_url = (result.get("metadata") or {}).get("url") or result.get("video_url")
                        if not video_url:
                            failed = True
                            break
                        try:
                            video_data = requests.get(video_url, timeout=300)
                            if video_data.status_code != 200 or not video_data.content:
                                print(f"  Download failed HTTP {video_data.status_code}")
                                failed = True
                                break
                            with open(path, "wb") as f:
                                f.write(video_data.content)
                            print(f"  Agnes key {idx} success")
                            return True
                        except Exception as dl_exc:
                            print(f"  Download error: {str(dl_exc)[:150]}")
                            failed = True
                            break

                    if status == "failed":
                        print(f"  Agnes key {idx} failed: {result.get('error', 'unknown')}")
                        failed = True
                        break

                    progress = result.get("progress", 0)
                    elapsed = int(time.time() - start)
                    print(f"  Agnes status: {status} ({progress}%) [{elapsed}s]")

                if failed:
                    continue

                # Timed out for this key/task — try next key
                print(f"  Agnes key {idx} poll timed out after {POLL_MAX_WAIT}s, trying next key...")

            except Exception as exc:
                print(f"  Agnes key {idx} error: {str(exc)[:200]}")
                continue

        if round_num < MAX_ROUNDS:
            print(f"  Round {round_num} done, waiting {ROUND_WAIT}s before retry...")
            time.sleep(ROUND_WAIT)

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
