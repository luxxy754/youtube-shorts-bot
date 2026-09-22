"""Sound effects + background music via ElevenLabs (keys rotate). Own music in assets/music wins."""
import glob
import os
import random
import subprocess

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSIC_MODEL = os.getenv("ELEVEN_MUSIC_MODEL", "music_v2")


def _keys():
    ks = [os.getenv(f"ELEVEN_KEY_{i}", "").strip() for i in (1, 2, 3)]
    return [k for k in ks if k]


def eleven_sound(text, seconds, path):
    """Generate a SOUND EFFECT. Returns True on success."""
    for key in _keys():
        try:
            r = requests.post(
                "https://api.elevenlabs.io/v1/sound-generation",
                headers={"xi-api-key": key},
                json={"text": text, "duration_seconds": seconds, "prompt_influence": 0.6},
                timeout=120)
            if r.status_code == 200 and r.content:
                with open(path, "wb") as f:
                    f.write(r.content)
                return True
            print(f"  ElevenLabs SFX HTTP {r.status_code}, trying next key")
        except Exception as exc:  # noqa: BLE001
            print(f"  ElevenLabs SFX error: {str(exc)[:150]}")
    return False


def eleven_music(prompt, seconds, path):
    """Real music model (POST /v1/music). The sound-generation model CANNOT write music -
    that is why the old background track sounded like noise."""
    ms = max(3000, min(int(seconds * 1000), 600000))
    for key in _keys():
        try:
            r = requests.post(
                "https://api.elevenlabs.io/v1/music",
                headers={"xi-api-key": key, "Accept": "audio/mpeg"},
                json={"prompt": prompt, "music_length_ms": ms, "model_id": MUSIC_MODEL},
                timeout=300)
            if r.status_code == 200 and r.content and len(r.content) > 5000:
                with open(path, "wb") as f:
                    f.write(r.content)
                print("  Music from ElevenLabs Music model")
                return True
            print(f"  ElevenLabs Music HTTP {r.status_code}, trying next key")
        except Exception as exc:  # noqa: BLE001
            print(f"  ElevenLabs Music error: {str(exc)[:150]}")
    return False


def get_music(prompt, path, seconds=20):
    # Best option by far: drop 3-5 royalty free mp3s in assets/music/ and they are used directly.
    own = glob.glob(os.path.join(ROOT, "assets", "music", "*.mp3"))
    if own:
        pick = random.choice(own)
        print(f"  Using own music: {os.path.basename(pick)}")
        return pick

    full = (f"{prompt}. Instrumental only, absolutely no vocals, no singing, no speech. "
            f"Light comedic cartoon underscore that sits behind sound effects, "
            f"consistent tempo, clean mix, gentle intro.")
    if eleven_music(full, seconds, path):
        return path

    print("  Music model unavailable - skipping music rather than using noise.")
    return None


def _mix(paths, out_path):
    """Mix 2+ short mp3s into one file. The sound-generation model handles ONE clean
    request much better than being asked to imagine two sounds "layered" together in
    a single prompt - that was producing muddy/garbled sfx. So we generate each sound
    separately and let ffmpeg do the actual layering."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for p in paths:
        cmd += ["-i", p]
    if len(paths) == 1:
        cmd += ["-c", "copy", out_path]
    else:
        cmd += ["-filter_complex",
                f"amix=inputs={len(paths)}:duration=longest:dropout_transition=0,"
                f"volume={len(paths)}", out_path]  # amix auto-attenuates; compensate
    subprocess.run(cmd, check=True)


def get_sfx(scenes, out_dir):
    """Returns list aligned with scenes: mp3 path or None.
    A cute cat sound (meow/purr/chirp) is always blended in, since that reads as
    warm and "mast" - not just whatever mechanical sfx the scene action implies."""
    CAT_SOUNDS = [
        "one single cute short cat meow, high pitched and adorable, clean isolated sound effect, no music, no speech",
        "a soft happy cat purring for a moment, clean isolated sound effect, no music, no speech",
        "a playful curious cat chirp/trill, friendly and cute, clean isolated sound effect, no music, no speech",
    ]
    out = []
    for i, sc in enumerate(scenes):
        action_text = (sc.get("sfx") or "").strip()
        cat_text = CAT_SOUNDS[i % len(CAT_SOUNDS)]
        cat_path = os.path.join(out_dir, f"sfx_{i}_cat.mp3")
        parts = [cat_path] if eleven_sound(cat_text, 1.5, cat_path) else []
        if action_text:
            action_full = f"{action_text}, clean isolated sound effect, no music, no speech"
            action_path = os.path.join(out_dir, f"sfx_{i}_action.mp3")
            if eleven_sound(action_full, 2.0, action_path):
                parts.append(action_path)
        if not parts:
            out.append(None)
            continue
        final = os.path.join(out_dir, f"sfx_{i}.mp3")
        try:
            _mix(parts, final)
            out.append(final)
        except Exception as exc:  # noqa: BLE001
            print(f"  sfx mix failed, using first part only: {str(exc)[:150]}")
            out.append(parts[0])
    return out
