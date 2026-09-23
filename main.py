"""Cat Shorts: story -> base image -> Magic Hour 15s video -> upload."""
import json
import os
import random
import subprocess
import time

import requests

from scripts.assemble import join_clips, mix
from scripts.audio import get_music, get_sfx, music_credit
from scripts.story import generate_story
from scripts.upload_youtube import have_credentials, upload_to_youtube
from scripts.video import (
    generate_15s_video,
    pollinations_image,
    static_video,
)

OUT = "output"
NUM_SCENES = int(os.getenv("NUM_SCENES", "1"))
MUSIC_VOLUME = float(os.getenv("MUSIC_VOLUME", "0.16"))


def build_metadata(story, credit=None):
    tags = [h.lstrip("#") for h in story.get("hashtags", [])]
    tags += [k for k in story.get("keywords", [])]
    title = story["title"].strip()
    if "#shorts" not in title.lower():
        title += " #shorts"
    desc = story.get("description", "").strip()
    desc += "\n\n" + " ".join(story.get("hashtags", []))
    desc += "\n\nKeywords: " + ", ".join(story.get("keywords", []))
    if credit:
        desc += f"\n\n{credit}"
    return title, desc, tags[:25]


def upload_image_to_public(image_path):
    """Upload image to a free public host. Tries 3 services in order."""
    # ---- Option 1: catbox.moe (most reliable, permanent) ----
    try:
        print("  Trying catbox.moe...")
        with open(image_path, "rb") as f:
            r = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": f},
                timeout=60,
            )
        if r.status_code == 200 and r.text.strip().startswith("http"):
            url = r.text.strip()
            print(f"  catbox.moe OK: {url}")
            return url
        print(f"  catbox.moe HTTP {r.status_code}: {r.text[:120]}")
    except Exception as exc:
        print(f"  catbox.moe failed: {str(exc)[:120]}")

    # ---- Option 2: tmpfiles.org ----
    try:
        print("  Trying tmpfiles.org...")
        with open(image_path, "rb") as f:
            r = requests.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": f},
                timeout=60,
            )
        if r.status_code == 200:
            data = r.json()
            url = data.get("data", {}).get("url", "")
            if url:
                # Convert to direct download link
                direct = url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                print(f"  tmpfiles.org OK: {direct}")
                return direct
        print(f"  tmpfiles.org HTTP {r.status_code}")
    except Exception as exc:
        print(f"  tmpfiles.org failed: {str(exc)[:120]}")

    # ---- Option 3: uguu.se ----
    try:
        print("  Trying uguu.se...")
        with open(image_path, "rb") as f:
            r = requests.post(
                "https://uguu.se/upload.php",
                files={"files[]": f},
                timeout=60,
            )
        if r.status_code == 200:
            data = r.json()
            files = data.get("files", [])
            if files and files[0].get("url"):
                url = files[0]["url"]
                print(f"  uguu.se OK: {url}")
                return url
        print(f"  uguu.se HTTP {r.status_code}")
    except Exception as exc:
        print(f"  uguu.se failed: {str(exc)[:120]}")

    print("  All image hosts failed")
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    story = generate_story(NUM_SCENES, frames_per_scene=6)

    # Use first scene as the hero scene
    scene = story["scenes"][0]
    print(f"\n=== Generating 15-second video ===")
    print(f"Prompt: {scene['visual'][:100]}...")

    # 1. Generate base image via Pollinations
    img_path = os.path.join(OUT, "hero.jpg")
    print("Generating base image...")
    if not pollinations_image(scene["visual"], img_path):
        print("Base image failed - aborting")
        return
    print(f"  Image: {img_path}")

    # 2. Upload image to get public URL
    print("Uploading image to public host...")
    image_url = upload_image_to_public(img_path)
    if not image_url:
        print("Public URL failed - aborting")
        return
    print(f"  Public URL: {image_url}")

    # 3. Generate 15-second video via Magic Hour
    print("Generating 15s video via Magic Hour...")
    t0 = time.time()
    video_path = os.path.join(OUT, "hero_15s.mp4")
    if not generate_15s_video(image_url, scene["visual"], video_path):
        print("Magic Hour failed - using static fallback")
        silent = os.path.join(OUT, "silent.mp3")
        try:
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "lavfi", "-t", "15", "-i", "anullsrc=r=44100:cl=stereo",
                "-c:a", "aac", silent,
            ], check=True, timeout=60)
            if not static_video(img_path, silent, video_path):
                print("Fallback also failed - aborting")
                return
        except Exception as exc:
            print(f"Fallback error: {str(exc)[:150]}")
            return
    print(f"  Video generated in {time.time() - t0:.1f}s")

    # 4. Get duration
    try:
        dur = float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nk=1:nw=1", video_path], text=True).strip())
    except Exception:
        dur = 15.0
    print(f"  Duration: {dur:.1f}s")

    # 5. Add cat sounds + music
    print("Adding cat sounds + music...")
    scenes_list = [scene]
    sfx = get_sfx(scenes_list, OUT)
    music = get_music(
        story.get("music", "playful cartoon music"),
        os.path.join(OUT, "music.mp3"),
        seconds=int(dur) + 2,
    )

    final = os.path.join(OUT, "final_short.mp4")
    try:
        mix(video_path, [dur], sfx, music, final, music_volume=MUSIC_VOLUME)
    except Exception as exc:
        print(f"  Mix failed: {str(exc)[:200]}")
        # If mix fails, just use the raw video
        import shutil
        shutil.copy(video_path, final)
    print(f"Final video: {final}")

    # 6. Metadata + upload
    title, desc, tags = build_metadata(story, music_credit(music))
    with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"title": title, "description": desc, "tags": tags},
                  f, ensure_ascii=False, indent=2)

    if os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"}:
        print("DRY_RUN: skipping upload.")
    elif not have_credentials():
        print("YT_* missing: skipping upload.")
    else:
        upload_to_youtube(final, title, desc, tags)


if __name__ == "__main__":
    main()
