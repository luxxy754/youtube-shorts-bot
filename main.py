"""Cat Shorts: story -> frames -> animation -> Wav2Lip -> mix -> upload."""
import json
import os
import random

from scripts.assemble import (
    frames_to_video, add_blink, apply_breathing,
    join_clips, mix,
)
from scripts.audio import eleven_dialogue, get_music, get_sfx, music_credit
from scripts.story import (
    generate_story, frame_prompt, scene_dialogue, scene_sfx,
)
from scripts.upload_youtube import have_credentials, upload_to_youtube
from scripts.video import (
    generate_scene_frames, pollinations_image,
    static_video, wav2lip_sync,
)

OUT = "output"
NUM_SCENES = int(os.getenv("NUM_SCENES", "4"))
FRAMES_PER_SCENE = int(os.getenv("FRAMES_PER_SCENE", "6"))
FPS = int(os.getenv("FPS", "8"))
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
    story = generate_story(NUM_SCENES, FRAMES_PER_SCENE)

    scene_videos = []
    scenes_used = []
    base_seed = random.randint(1, 10**6)

    for i, sc in enumerate(story["scenes"]):
        print(f"\n=== Scene {i+1}/{len(story['scenes'])} ===")

        # 1. Generate N frames
        print(f"Generating {FRAMES_PER_SCENE} frames...")
        def make_prompt(fi):
            return frame_prompt(story, i, fi, FRAMES_PER_SCENE)

        frames = generate_scene_frames(
            make_prompt, i, FRAMES_PER_SCENE, OUT, base_seed
        )
        if not frames:
            print("  SKIP: no frames generated")
            continue

        # 2. Compile frames to video
        anim_vid = os.path.join(OUT, f"scene_{i}_anim.mp4")
        if not frames_to_video(frames, anim_vid, fps=FPS):
            print("  SKIP: frame compilation failed")
            continue

        # 3. Generate dialogue audio
        aud_path = os.path.join(OUT, f"scene_{i}.mp3")
        dialogue = scene_dialogue(story, i)
        if not eleven_dialogue(dialogue, aud_path):
            print("  SKIP: dialogue audio failed")
            continue

        # 4. Wav2Lip on first frame (for lipsync)
        main_img = frames[0]
        talk_vid = os.path.join(OUT, f"scene_{i}_talk.mp4")
        if wav2lip_sync(main_img, aud_path, talk_vid):
            # Replace animation's first frame with talking version? No -
            # simpler: just use the animation + audio, Wav2Lip is too slow per frame.
            # Instead, use animation video + audio track separately.
            pass

        # 5. Combine animation video with audio
        final_scene = os.path.join(OUT, f"scene_{i}_final.mp4")
        try:
            import subprocess
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", anim_vid, "-i", aud_path,
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                "-movflags", "+faststart",
                final_scene,
            ], check=True, timeout=120)
            scene_videos.append(final_scene)
            scenes_used.append(sc)
            print(f"  Scene {i+1} DONE")
        except Exception as exc:
            print(f"  Scene {i+1} merge failed: {str(exc)[:200]}")
            continue

    if not scene_videos:
        print("\nWARNING: No scene video created. Skipping run.")
        return

    print(f"\nConcatenating {len(scene_videos)} scenes...")
    joined, durs = join_clips(scene_videos, OUT)

    print("Adding music + sfx...")
    sfx = get_sfx(scenes_used, OUT)
    music = get_music(
        story.get("music", "playful cartoon background music"),
        os.path.join(OUT, "music.mp3"),
        seconds=max(8, int(sum(durs)) + 2),
    )

    final = os.path.join(OUT, "final_short.mp4")
    try:
        mix(joined, durs, sfx, music, final, music_volume=MUSIC_VOLUME)
    except Exception as exc:
        print(f"  Mix failed: {str(exc)[:200]}, retry without music")
        music = None
        try:
            mix(joined, durs, sfx, music, final, music_volume=MUSIC_VOLUME)
        except Exception as exc2:
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
