"""Sound effects + background music via ElevenLabs (keys rotate). Own music in assets/music wins."""
import glob
import os
import random

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _keys():
    ks = [os.getenv(f"ELEVEN_KEY_{i}", "").strip() for i in (1, 2, 3)]
    return [k for k in ks if k]


def eleven_sound(text, seconds, path):
    """Generate a sound effect / music clip. Returns True on success."""
    for key in _keys():
        try:
            r = requests.post(
                "https://api.elevenlabs.io/v1/sound-generation",
                headers={"xi-api-key": key},
                json={"text": text, "duration_seconds": seconds, "prompt_influence": 0.5},
                timeout=120)
            if r.status_code == 200 and r.content:
                with open(path, "wb") as f:
                    f.write(r.content)
                return True
            print(f"  ElevenLabs HTTP {r.status_code}, trying next key")
        except Exception as exc:  # noqa: BLE001
            print(f"  ElevenLabs error: {str(exc)[:150]}")
    return False


def get_music(prompt, path):
    own = glob.glob(os.path.join(ROOT, "assets", "music", "*.mp3"))
    if own:
        pick = random.choice(own)
        print(f"  Using own music: {os.path.basename(pick)}")
        return pick
    if eleven_sound(f"{prompt}, instrumental, seamless loop, no vocals", 20, path):
        return path
    return None


def get_sfx(scenes, out_dir):
    """Returns list aligned with scenes: mp3 path or None."""
    out = []
    for i, sc in enumerate(scenes):
        text = (sc.get("sfx") or "").strip()
        path = os.path.join(out_dir, f"sfx_{i}.mp3")
        out.append(path if text and eleven_sound(text, 3, path) else None)
    return out
