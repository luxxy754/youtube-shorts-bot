"""Audio: Hindi/Urdu dialogue TTS + SFX + background music via ElevenLabs."""
import glob
import hashlib
import os
import random
import subprocess

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSIC_MODEL = os.getenv("ELEVEN_MUSIC_MODEL", "music_v2")

# Default voice IDs - replace with Hindi/Urdu-capable voice IDs from
# your ElevenLabs Voice Library (https://elevenlabs.io/voice-library).
# These are placeholders; use voice IDs that sound good for Hindi/Urdu.
HINDI_VOICE_IDS = [
    os.getenv("ELEVEN_VOICE_HINDI_1", "pNInz6obpgDQGcFmaJgB"),  # Adam
    os.getenv("ELEVEN_VOICE_HINDI_2", "EXAVITQu4vr4xnSDxMaL"),  # Bella
    os.getenv("ELEVEN_VOICE_HINDI_3", "TxGEqnHWrfWFTfGW9XjX"),  # Josh
]


def _keys():
    ks = [os.getenv(f"ELEVEN_KEY_{i}", "").strip() for i in (1, 2, 3)]
    return [k for k in ks if k]


def _cache_dir():
    d = os.path.join(ROOT, "output", "audio_cache")
    os.makedirs(d, exist_ok=True)
    return d


def eleven_dialogue(text, path, voice_id=None):
    """Generate Hindi/Urdu speech for a dialogue line. Returns True on success."""
    if not text.strip():
        return False

    # Cache hit?
    cache_key = hashlib.md5(f"{text}|{voice_id}".encode()).hexdigest()
    cache_path = os.path.join(_cache_dir(), f"{cache_key}.mp3")
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
        with open(cache_path, "rb") as src, open(path, "wb") as dst:
            dst.write(src.read())
        print(f"  Dialogue cache hit: {text[:40]}...")
        return True

    vid = voice_id or random.choice(HINDI_VOICE_IDS)
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"
    payload = {
        "text": text,
        "model_id": os.getenv("ELEVEN_TTS_MODEL", "eleven_multilingual_v2"),
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.4,
            "use_speaker_boost": True,
        },
    }

    for key in _keys():
        try:
            r = requests.post(
                url,
                headers={"xi-api-key": key, "Accept": "audio/mpeg",
                         "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            if r.status_code == 200 and r.content and len(r.content) > 1000:
                with open(path, "wb") as f:
                    f.write(r.content)
                with open(cache_path, "wb") as f:
                    f.write(r.content)
                print(f"  Dialogue OK: {text[:40]}...")
                return True
            print(f"  TTS HTTP {r.status_code} on key {_keys().index(key)+1}")
        except Exception as exc:  # noqa: BLE001
            print(f"  TTS error: {str(exc)[:150]}")
    return False


def eleven_sound(text, seconds, path):
    """Generate a SOUND EFFECT via ElevenLabs."""
    for key in _keys():
        try:
            r = requests.post(
                "https://api.elevenlabs.io/v1/sound-generation",
                headers={"xi-api-key": key},
                json={"text": text, "duration_seconds": seconds,
                      "prompt_influence": 0.6},
                timeout=120)
            if r.status_code == 200 and r.content:
                with open(path, "wb") as f:
                    f.write(r.content)
                return True
            print(f"  SFX HTTP {r.status_code}, trying next key")
        except Exception as exc:  # noqa: BLE001
            print(f"  SFX error: {str(exc)[:150]}")
    return False


def eleven_music(prompt, seconds, path):
    """Generate background music."""
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
            print(f"  Music HTTP {r.status_code}, trying next key")
        except Exception as exc:  # noqa: BLE001
            print(f"  Music error: {str(exc)[:150]}")
    return False


def _valid_audio(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", path],
            capture_output=True, text=True, timeout=30)
        return out.returncode == 0 and float(out.stdout.strip() or 0) > 0.5
    except Exception:  # noqa: BLE001
        return False


def get_music(prompt, path, seconds=20):
    own = glob.glob(os.path.join(ROOT, "assets", "music", "*.mp3"))
    own += glob.glob(os.path.join(ROOT, "*.mp3"))
    good = [p for p in own if _valid_audio(p)]
    if good:
        pick = random.choice(good)
        print(f"  Using own music: {os.path.basename(pick)}")
        return pick

    full = (f"{prompt}. Instrumental only, no vocals, no singing, no speech. "
            f"Light comedic cartoon underscore, consistent tempo, clean mix.")
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
    """List of SFX mp3 paths aligned with scenes (or None)."""
    CAT_SOUNDS = [
        "a short cute cartoon pop, isolated, no music",
        "a soft happy cartoon sparkle chime, isolated, no music",
        "a playful cartoon boing sound, isolated, no music",
    ]
    out = []
    for i, sc in enumerate(scenes):
        action_text = (sc.get("sfx") or "").strip()
        cat_text = CAT_SOUNDS[i % len(CAT_SOUNDS)]
        cat_path = os.path.join(out_dir, f"sfx_{i}_primary.mp3")
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
        except Exception as exc:  # noqa: BLE001
            print(f"  sfx mix failed, using first part: {str(exc)[:150]}")
            out.append(parts[0])
    return out
