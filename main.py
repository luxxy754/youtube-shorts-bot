"""Cat Shorts: story -> frames (parallel) -> animation -> sounds -> upload."""
import json
import os
import random
import subprocess

from scripts.assemble import frames_to_video, join_clips, mix
from scripts.audio import get_music, get_sfx, music_credit
from scripts.story import generate_story, frame_prompt
from scripts.upload_youtube import have_credentials, upload_to_youtube
from scripts.video import generate_all_frames

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

    # ---- Build ALL frame tasks ----
    base_seed = random.randint(1, 10**6)
    all_tasks = []
    scenes_data = []  # (scene_index, scene_dict)

    for i, sc in enumerate(story["scenes"]):
        scenes_data.append((i, sc))
        for f in range(FRAMES_PER_SCENE):
            prompt = frame_prompt(story, i, f, FRAMES_PER_SCENE)
            fp = os.path.join(OUT, f"scene_{i}_frame_{f}.jpg")
            seed = base_seed + i * 1000 + f
            all_tasks.append((i, f, prompt, fp, seed))

    # ---- Generate ALL frames in ONE parallel batch ----
    print(f"\n=== Generating all {len(all_tasks)} images in parallel ===")
    t0 = __import__("time").time()
    results = generate_all_frames(all_tasks, OUT)
    t1 = __import__("time").time()
    print(f"  All images done in {t1 - t0:.1f}s")

    # ---- Build per-scene frame lists ----
    scene_videos = []
    scenes_used = []

    for i, sc in scenes_data:
        frames = []
        for f in range(FRAMES_PER_SCENE):
            fp = os.path.join(OUT, f"scene_{i}_frame_{f}.jpg")
            if results.get((i, f)) and os.path.exists(fp):
                frames.append(fp)
            elif frames:
                frames.append(frames[-1])  # repeat previous

        if not frames:
            print(f"  Scene {i+1}: no frames, skipping")
            continue

        # Frames -> animation
        anim_vid = os.path.join(OUT, f"scene_{i}_anim.mp4")
        if not frames_to_video(frames, anim_vid, fps=FPS):
            print(f"  Scene {i+1}: frame compile failed")
            continue

        # Add silent audio
        silent_vid = os.path.join(OUT, f"scene_{i}_silent.mp4")
        try:
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", anim_vid,
                "-f", "lavfi", "-t", str(SCENE_SECONDS),
                "-i", "anullsrc=r=44100:cl=stereo",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart",
                silent_vid,
            ], check=True, timeout=120)
            scene_videos.append(silent_vid)
            scenes_used.append(sc)
            print(f"  Scene {i+1} DONE")
        except Exception as exc:
            print(f"  Scene {i+1} silent merge failed: {str(exc)[:150]}")

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
