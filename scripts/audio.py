"""Audio: cat sounds only (no dialogue, no TTS).

Cat meows/purrs/chirps via ElevenLabs SFX, plus background music.
Falls back to local mp3s if ElevenLabs unavailable.
"""
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


def _valid_audio(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", path],
            capture_output=True, text=True, timeout=30)
        return out.returncode == 0 and float(out.stdout.strip() or 0) > 0.3
    except Exception:
        return False


def cat_sound(text, seconds, path):
    """Generate a cat sound via ElevenLabs SFX."""
    for key in _keys():
        try:
            r = requests.post(
                "https://api.elevenlabs.io/v1/sound-generation",
                headers={"xi-api-key": key},
                json={"text": text, "duration_seconds": seconds,
                      "prompt_influence": 0.7},
                timeout=120)
            if r.status_code == 200 and r.content:
                with open(path, "wb") as f:
                    f.write(r.content)
                return True
        except Exception as exc:
            print(f"  Cat sound error: {str(exc)[:150]}")
    return False


def eleven_music(prompt, seconds, path):
    """Background music via ElevenLabs."""
    ms = max(3000, min(int(seconds * 1000), 600000))
    for key in _keys():
        try:
            r = requests.post(
                "https://api.elevenlabs.io/v1/music",
                headers={"xi-api-key": key, "Accept": "audio/mpeg"},
                json={"prompt": prompt, "music_length_ms": ms,
                      "model_id": MUSIC_MODEL},
                timeout=300)
            if r.status_code == 200 and r.content and len(r.content) > 5000:
                with open(path, "wb") as f:
                    f.write(r.content)
                print("  Music from ElevenLabs")
                return True
        except Exception as exc:
            print(f"  Music error: {str(exc)[:150]}")
    return False


def get_music(prompt, path, seconds=20):
    # Local mp3s first
    own = glob.glob(os.path.join(ROOT, "assets", "music", "*.mp3"))
    own += glob.glob(os.path.join(ROOT, "*.mp3"))
    good = [p for p in own if _valid_audio(p)]
    if good:
        pick = random.choice(good)
        print(f"  Using own music: {os.path.basename(pick)}")
        return pick

    full = (f"{prompt}. Instrumental only, no vocals, no singing, no speech. "
            f"Light comedic cartoon underscore, clean mix.")
    if eleven_music(full, seconds, path):
        return path

    print("  Music unavailable - skipping music.")
    return None


def music_credit(path):
    if not path:
        return None
    name = os.path.basename(path)
    for credits_file in (os.path.join(ROOT, "assets", "music", "credits.txt"),
                         os.path.join(ROOT, "credits.txt")):
        if not os.path.exists(credits_file):
            continue
        try:
            with open(credits_file, encoding="utf-8") as f:
                for line in f:
                    if "=" not in line:
                        continue
                    fname, credit = line.split("=", 1)
                    if fname.strip() == name:
                        return credit.strip()
        except OSError:
            pass
    return None


def get_sfx(scenes, out_dir):
    """Cat sounds for each scene. Returns list of mp3 paths or None."""
    # Rotate cat sounds so variety
    CAT_SOUNDS = [
        "one cute short cat meow, high pitched, isolated, no music, no speech",
        "a soft happy cat purr, clean, isolated, no music",
        "a playful curious cat chirp or trill, isolated, no music",
        "a surprised short cat meow, cute, isolated, no music",
        "a happy short cat meow, warm, isolated, no music",
    ]
    out = []
    for i, sc in enumerate(scenes):
        action_text = (sc.get("sfx") or "").strip()
        base_text = CAT_SOUNDS[i % len(CAT_SOUNDS)]

        # Primary: cute cat sound
        primary_path = os.path.join(out_dir, f"sfx_{i}_primary.mp3")
        parts = []
        if cat_sound(base_text, 1.5, primary_path):
            parts.append(primary_path)

        # Optional: scene-specific action sound
        if action_text:
            action_full = f"{action_text}, clean isolated sound effect, no music, no speech"
            action_path = os.path.join(out_dir, f"sfx_{i}_action.mp3")
            if cat_sound(action_full, 1.5, action_path):
                parts.append(action_path)

        if not parts:
            out.append(None)
            continue

        final = os.path.join(out_dir, f"sfx_{i}.mp3")
        try:
            if len(parts) == 1:
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                                "-i", parts[0], "-c", "copy", final], check=True)
            else:
                cmd = ["ffmpeg", "-y", "-loglevel", "error"]
                for p in parts:
                    cmd += ["-i", p]
                cmd += ["-filter_complex",
                        f"amix=inputs={len(parts)}:duration=longest:dropout_transition=0,"
                        f"volume={len(parts)}", final]
                subprocess.run(cmd, check=True)
            out.append(final)
        except Exception as exc:
            print(f"  sfx mix failed: {str(exc)[:150]}")
            out.append(parts[0])
    return out
