"""Cat Shorts: story -> frames -> animation -> cat sounds + music -> upload."""
import json
import os
import random
import subprocess

from scripts.assemble import frames_to_video, join_clips, mix
from scripts.audio import get_music, get_sfx, music_credit
from scripts.story import generate_story, frame_prompt, scene_sfx
from scripts.upload_youtube import have_credentials, upload_to_youtube
from scripts.video import generate_scene_frames

OUT = "output"
NUM_SCENES = int(os.getenv("NUM_SCENES", "4"))
FRAMES_PER_SCENE = int(os.getenv("FRAMES_PER_SCENE", "6"))
FPS = int(os.getenv("FPS", "8"))
MUSIC_VOLUME = float(os.getenv("MUSIC_VOLUME", "0.16"))
SCENE_SECONDS = float(os.getenv("SCENE_SECONDS", "4.0"))


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

        # 1. Generate frames
        print(f"Generating {FRAMES_PER_SCENE} frames...")

        def make_prompt(fi):
            return frame_prompt(story, i, fi, FRAMES_PER_SCENE)

        frames = generate_scene_frames(
            make_prompt, i, FRAMES_PER_SCENE, OUT, base_seed
        )
        if not frames:
            print("  SKIP: no frames generated")
            continue

        # 2. Frames -> animation video
        anim_vid = os.path.join(OUT, f"scene_{i}_anim.mp4")
        if not frames_to_video(frames, anim_vid, fps=FPS):
            print("  SKIP: frame compilation failed")
            continue

        # 3. Add silent audio track (so concat works)
        silent_vid = os.path.join(OUT, f"scene_{i}_silent.mp4")
        try:
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", anim_vid,
                "-f", "lavfi", "-t", str(SCENE_SECONDS), "-i", "anullsrc=r=44100:cl=stereo",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart",
                silent_vid,
            ], check=True, timeout=120)
            scene_videos.append(silent_vid)
            scenes_used.append(sc)
            print(f"  Scene {i+1} DONE")
        except Exception as exc:
            print(f"  Scene {i+1} silent merge failed: {str(exc)[:200]}")
            continue

    if not scene_videos:
        print("\nWARNING: No scene video created. Skipping run.")
        return

    print(f"\nConcatenating {len(scene_videos)} scenes...")
    joined, durs = join_clips(scene_videos, OUT)

    print("Adding cat sounds + music...")
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
            print(f"  Mix without music failed: {str(exc2)[:200]}")
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
