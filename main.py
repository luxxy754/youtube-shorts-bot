"""AI Shorts bot: story -> 3D animated clips -> sfx + music -> upload."""
import json
import os
import random

from scripts.assemble import join_clips, mix
from scripts.audio import get_music, get_sfx, music_credit
from scripts.story import generate_story, scene_prompt
from scripts.upload_youtube import have_credentials, upload_to_youtube
from scripts.video import CLIP_SECONDS, make_clip

OUT = "output"
NUM_SCENES = int(os.getenv("NUM_SCENES", "3"))
MUSIC_VOLUME = float(os.getenv("MUSIC_VOLUME", "0.30"))


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

    clips = []
    seed = random.randint(1, 10**6)
    for i, sc in enumerate(story["scenes"]):
        print(f"Scene {i + 1}/{len(story['scenes'])}: {sc['visual']}")
        path = os.path.join(OUT, f"clip_{i}.mp4")
        if make_clip(scene_prompt(story, i), path, seed + i):
            clips.append((path, sc))
        else:
            print("  Scene skipped (all providers failed)")
    if not clips:
        raise RuntimeError("No clip could be generated. Check REPLICATE_API_TOKEN / credits.")

    scenes = [sc for _, sc in clips]
    joined, durs = join_clips([p for p, _ in clips], OUT, CLIP_SECONDS + 1)

    print("Audio...")
    sfx = get_sfx(scenes, OUT)
    music = get_music(story.get("music", "playful cartoon background music"),
                      os.path.join(OUT, "music.mp3"),
                      seconds=max(8, int(sum(durs)) + 2))
    final = os.path.join(OUT, "final_short.mp4")
    try:
        mix(joined, durs, sfx, music, final, music_volume=MUSIC_VOLUME)
    except Exception as exc:  # noqa: BLE001
        print(f"  Mix with music failed ({str(exc)[:200]}), retrying without music")
        music = None
        try:
            mix(joined, durs, sfx, music, final, music_volume=MUSIC_VOLUME)
        except Exception as exc2:  # noqa: BLE001
            print(f"  Mix with sfx failed too ({str(exc2)[:200]}), retrying silent")
            sfx = [None] * len(sfx)
            mix(joined, durs, sfx, music, final, music_volume=MUSIC_VOLUME)
    print(f"Video ready: {final} ({sum(durs):.1f}s)")

    title, desc, tags = build_metadata(story, music_credit(music))
    with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"title": title, "description": desc, "tags": tags}, f, ensure_ascii=False, indent=2)

    if os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"}:
        print("DRY_RUN on: skipping upload.")
    elif not have_credentials():
        print("YT_* secrets missing: skipping upload.")
    else:
        upload_to_youtube(final, title, desc, tags)


if __name__ == "__main__":
    main()
