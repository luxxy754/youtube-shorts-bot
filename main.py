"""AI Pet Drama Shorts: story -> images -> motion -> voice -> upload."""
import json
import os
import shutil
import subprocess
import time

from scripts.assemble import join_clips, mix
from scripts.audio import (
    generate_dialogue_audio,
    get_music,
    get_sfx,
    music_credit,
)
from scripts.story import (
    generate_story,
    scene_dialogue,
    scene_prompt,
    scene_sfx,
)
from scripts.upload_youtube import have_credentials, upload_to_youtube
from scripts.video import CLIP_SECONDS, make_motion_clip, pollinations_image

OUT = "output"
NUM_SCENES = int(os.getenv("NUM_SCENES", "4"))
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
    print("=" * 60)
    print("PET DRAMA SHORTS - STARTING")
    print("=" * 60)
    os.makedirs(OUT, exist_ok=True)

    print("\n[1/5] Generating story...")
    story = generate_story(NUM_SCENES)

    print("\n[2/5] Generating scene images + motion clips...")
    scene_clips = []
    scenes_used = []

    for i, sc in enumerate(story["scenes"]):
        print(f"\n--- Scene {i + 1}/{len(story['scenes'])} ---")

        img_path = os.path.join(OUT, f"scene_{i}.jpg")
        print(f"  Image: {sc['visual'][:60]}...")
        if not pollinations_image(scene_prompt(story, i), img_path, seed=int(time.time()) + i):
            print("  SKIP: image failed")
            continue

        # Dialogue audio (edge-tts)
        aud_path = os.path.join(OUT, f"scene_{i}_voice.mp3")
        dialogue = scene_dialogue(story, i)
        print(f"  Dialogue: {dialogue}")
        if not generate_dialogue_audio(dialogue, aud_path):
            print("  SKIP: voice failed")
            continue

        # Motion clip from image
        clip_path = os.path.join(OUT, f"scene_{i}_motion.mp4")
        if not make_motion_clip(img_path, clip_path, scene_idx=i, duration=CLIP_SECONDS):
            print("  SKIP: motion clip failed")
            continue

        # Merge audio with video
        final_clip = os.path.join(OUT, f"scene_{i}_final.mp4")
        try:
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", clip_path, "-i", aud_path,
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart",
                final_clip,
            ], check=True, timeout=120)
            scene_clips.append(final_clip)
            scenes_used.append(sc)
            print(f"  Scene {i + 1} DONE")
        except Exception as exc:
            print(f"  Merge failed: {str(exc)[:150]}")

    if not scene_clips:
        print("\nFAILED: No scene clips created")
        return

    print(f"\n[3/5] Concatenating {len(scene_clips)} scenes...")
    joined, durs = join_clips(scene_clips, OUT)

    print("\n[4/5] Adding pet sounds + music...")
    sfx = get_sfx(scenes_used, OUT)
    music = get_music(
        story.get("music", "playful cartoon music"),
        os.path.join(OUT, "music.mp3"),
        seconds=int(sum(durs)) + 2,
    )

    final = os.path.join(OUT, "final_short.mp4")
    try:
        mix(joined, durs, sfx, music, final, music_volume=MUSIC_VOLUME)
        print(f"  Final: {final}")
    except Exception as exc:
        print(f"  Mix failed: {str(exc)[:200]}")
        shutil.copy(joined, final)

    print(f"  Duration: {sum(durs):.1f}s")

    print("\n[5/5] Uploading to YouTube...")
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

    print("=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
