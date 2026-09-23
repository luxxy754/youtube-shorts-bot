"""Cat Shorts: story -> base image -> Magic Hour 15s video -> upload."""
import json
import os
import shutil
import subprocess
import time

from scripts.assemble import mix
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


def main():
    os.makedirs(OUT, exist_ok=True)
    story = generate_story(NUM_SCENES, frames_per_scene=6)

    # Hero scene = first scene
    scene = story["scenes"][0]
    print(f"\n=== Generating 15-second video ===")
    print(f"Prompt: {scene['visual'][:100]}...")

    # 1. Generate base image via Pollinations
    img_path = os.path.join(OUT, "hero.jpg")
    print("Generating base image...")
    if not pollinations_image(scene["visual"], img_path):
        print("Base image failed - aborting")
        return
    print(f"  Image saved: {img_path}")

    # 2. Generate 15-second video via Magic Hour
    #    (Magic Hour uploads the image internally - no public URL needed)
    print("Generating 15s video via Magic Hour...")
    t0 = time.time()
    video_path = os.path.join(OUT, "hero_15s.mp4")

    magic_hour_ok = generate_15s_video(img_path, scene["visual"], video_path)

    if not magic_hour_ok:
        print("Magic Hour failed - using static fallback")
        silent = os.path.join(OUT, "silent.mp3")
        try:
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "lavfi", "-t", "15",
                "-i", "anullsrc=r=44100:cl=stereo",
                "-c:a", "aac", silent,
            ], check=True, timeout=60)
            if not static_video(img_path, silent, video_path):
                print("Fallback also failed - aborting")
                return
        except Exception as exc:
            print(f"Fallback error: {str(exc)[:150]}")
            return

    print(f"  Video ready in {time.time() - t0:.1f}s")

    # 3. Get duration
    try:
        dur = float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nk=1:nw=1", video_path], text=True).strip())
    except Exception:
        dur = 15.0
    print(f"  Duration: {dur:.1f}s")

    # 4. Add cat sounds + music
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
        print(f"Final video: {final}")
    except Exception as exc:
        print(f"  Mix failed: {str(exc)[:200]}")
        # Fallback: use raw video without SFX/music
        shutil.copy(video_path, final)
        print(f"  Using raw video: {final}")

    # 5. Save metadata
    title, desc, tags = build_metadata(story, music_credit(music))
    with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"title": title, "description": desc, "tags": tags},
                  f, ensure_ascii=False, indent=2)

    # 6. Upload to YouTube
    if os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"}:
        print("DRY_RUN: skipping upload.")
    elif not have_credentials():
        print("YT_* missing: skipping upload.")
    else:
        upload_to_youtube(final, title, desc, tags)


if __name__ == "__main__":
    main()
