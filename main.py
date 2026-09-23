"""Talking Vegetables Shorts: story -> images -> dialogue -> lipsync -> motion -> upload."""
import json
import os
import random

from scripts.assemble import join_clips, mix
from scripts.audio import eleven_dialogue, get_music, get_sfx, music_credit
from scripts.story import generate_story, scene_dialogue, scene_prompt, scene_sfx
from scripts.upload_youtube import have_credentials, upload_to_youtube
from scripts.video import (
    pollinations_image,
    static_video,
    wav2lip_sync,
)

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
    os.makedirs(OUT, exist_ok=True)
    story = generate_story(NUM_SCENES)

    scene_videos = []
    scenes_used = []
    seed = random.randint(1, 10**6)
    total_scenes = len(story["scenes"])

    for i, sc in enumerate(story["scenes"]):
        print(f"\n=== Scene {i+1}/{total_scenes} ===")
        print(f"Visual:   {sc['visual'][:90]}...")
        print(f"Dialogue: {sc.get('dialogue', '')}")

        img_path = os.path.join(OUT, f"scene_{i}.jpg")
        aud_path = os.path.join(OUT, f"scene_{i}.mp3")
        vid_path = os.path.join(OUT, f"scene_{i}_talk.mp4")

        # 1. Image
        if not pollinations_image(scene_prompt(story, i), img_path):
            print("  SKIP: image generation failed")
            continue

        # 2. Dialogue audio
        dialogue = scene_dialogue(story, i)
        if not eleven_dialogue(dialogue, aud_path):
            print("  SKIP: dialogue audio failed")
            continue

        # 3. Wav2Lip lipsync, fallback to static
        if wav2lip_sync(img_path, aud_path, vid_path):
            scene_videos.append(vid_path)
            scenes_used.append(sc)
        elif static_video(img_path, aud_path, vid_path):
            print("  Wav2Lip failed, using static+audio fallback")
            scene_videos.append(vid_path)
            scenes_used.append(sc)
        else:
            print("  SKIP: video assembly failed")

    if not scene_videos:
        print("\nWARNING: No scene video could be created. Skipping this run.")
        return

    print(f"\nConcatenating {len(scene_videos)} clips...")
    joined, durs = join_clips(scene_videos, OUT)

    print("Adding background music + sfx...")
    sfx = get_sfx(scenes_used, OUT)
    music = get_music(
        story.get("music", "playful cartoon background music"),
        os.path.join(OUT, "music.mp3"),
        seconds=max(8, int(sum(durs)) + 2),
    )

    final = os.path.join(OUT, "final_short.mp4")
    try:
        mix(joined, durs, sfx, music, final, music_volume=MUSIC_VOLUME)
    except Exception as exc:  # noqa: BLE001
        print(f"  Mix failed ({str(exc)[:200]}), retrying without music")
        music = None
        try:
            mix(joined, durs, sfx, music, final, music_volume=MUSIC_VOLUME)
        except Exception as exc2:  # noqa: BLE001
            print(f"  Mix without music failed too: {str(exc2)[:200]}")
            return

    print(f"Video ready: {final} ({sum(durs):.1f}s)")

    title, desc, tags = build_metadata(story, music_credit(music))
    with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"title": title, "description": desc, "tags": tags},
                  f, ensure_ascii=False, indent=2)

    if os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"}:
        print("DRY_RUN: skipping upload.")
    elif not have_credentials():
        print("YT_* secrets missing: skipping upload.")
    else:
        upload_to_youtube(final, title, desc, tags)


if __name__ == "__main__":
    main()
