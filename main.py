"""Cat Shorts: story -> base image -> Magic Hour 15s video -> upload."""
import json
import os
import random
import subprocess
import time

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
NUM_SCENES = int(os.getenv("NUM_SCENES", "1"))  # One hero scene -> one 15s video
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
    """Magic Hour needs a public URL. Upload to 0x0.st (free)."""
    try:
        with open(image_path, "rb") as f:
            r = requests.post(
                "https://0x0.st",
                files={"file": f},
                headers={"User-Agent": "cat-shorts-bot/1.0"},
                timeout=60,
            )
        if r.status_code == 200 and r.text.startswith("http"):
            return r.text.strip()
    except Exception as exc:
        print(f"  Image upload failed: {str(exc)[:150]}")
    return None


import requests  # noqa: E402


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

    # 2. Upload image to get public URL
    print("Uploading image to public host...")
    image_url = upload_image_to_public(img_path)
    if not image_url:
        print("Public URL failed - aborting")
        return
    print(f"  URL: {image_url}")

    # 3. Generate 15-second video via Magic Hour
    print("Generating 15s video via Magic Hour...")
    t0 = time.time()
    video_path = os.path.join(OUT, "hero_15s.mp4")
    if not generate_15s_video(image_url, scene["visual"], video_path):
        print("Magic Hour failed - using static fallback")
        # Fallback: static image + 15s silence
        silent = os.path.join(OUT, "silent.mp3")
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-t", "15", "-i", "anullsrc=r=44100:cl=stereo",
            "-c:a", "aac", silent,
        ], check=True)
        if not static_video(img_path, silent, video_path):
            print("Fallback also failed - aborting")
            return
    print(f"  Video generated in {time.time() - t0:.1f}s")

    # 4. Get duration
    dur = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nk=1:nw=1", video_path], text=True).strip())
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
        return
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
