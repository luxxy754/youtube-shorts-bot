"""Audio: Hindi/Urdu dialogue via edge-tts + optional pet sounds."""
import asyncio
import glob
import hashlib
import os
import random
import subprocess

import edge_tts
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VOICE_MAP = {
    "hi": {"female": "hi-IN-SwaraNeural", "male": "hi-IN-MadhurNeural"},
    "ur": {"female": "ur-PK-UzmaNeural", "male": "ur-PK-AsadNeural"},
}
DEFAULT_LANG = os.getenv("TTS_LANG", "hi")
DEFAULT_GENDER = os.getenv("TTS_GENDER", "female")
DEFAULT_RATE = os.getenv("TTS_RATE", "-8%")     # slower, more expressive
DEFAULT_PITCH = os.getenv("TTS_PITCH", "+3Hz")  # higher, more dramatic


def _cache_dir():
    d = os.path.join(ROOT, "output", "audio_cache")
    os.makedirs(d, exist_ok=True)
    return d


def _voice_id(lang=None, gender=None):
    lang = lang or DEFAULT_LANG
    gender = gender or DEFAULT_GENDER
    return VOICE_MAP.get(lang, VOICE_MAP["hi"]).get(gender, VOICE_MAP["hi"]["female"])


async def _tts_save(text, voice, rate, pitch, out_path):
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(out_path)


def generate_dialogue_audio(text, path):
    """Hindi/Urdu speech via edge-tts with emotional tone."""
    if not text.strip():
        return False

    # Add dramatic pause markers
    enhanced = text.strip()
    if enhanced[-1] not in ".!?":
        enhanced += "!"

    cache_key = hashlib.md5(enhanced.encode()).hexdigest()
    cache_path = os.path.join(_cache_dir(), f"{cache_key}.mp3")
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
        with open(cache_path, "rb") as src, open(path, "wb") as dst:
            dst.write(src.read())
        return True

    voice = _voice_id()
    try:
        asyncio.run(_tts_save(enhanced, voice, DEFAULT_RATE, DEFAULT_PITCH, path))
    except Exception as exc:
        print(f"  edge-tts err: {str(exc)[:200]}")
        try:
            asyncio.run(_tts_save(enhanced, VOICE_MAP["hi"]["male"],
                                   DEFAULT_RATE, DEFAULT_PITCH, path))
        except Exception:
            return False

    if os.path.exists(path) and os.path.getsize(path) > 1000:
        with open(cache_path, "wb") as f:
            with open(path, "rb") as src:
                f.write(src.read())
        print(f"  Voice OK ({os.path.getsize(path)//1024} KB)")
        return True
    return False


def _keys():
    ks = []
    for i in (1, 2, 3):
        k = os.getenv(f"ELEVEN_KEY_{i}", "").strip()
        if k:
            ks.append(k)
    return ks


def eleven_sound(text, seconds, path):
    """Pet sound via ElevenLabs (optional)."""
    keys = _keys()
    if not keys:
        return False
    for key in keys:
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
        except Exception:
            continue
    return False


def _valid_audio(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", path],
            capture_output=True, text=True, timeout=30)
        return out.returncode == 0 and float(out.stdout.strip() or 0) > 0.5
    except Exception:
        return False


def get_music(prompt, path, seconds=20):
    own = glob.glob(os.path.join(ROOT, "assets", "music", "*.mp3"))
    good = [p for p in own if _valid_audio(p)]
    if good:
        pick = random.choice(good)
        print(f"  Using own music: {os.path.basename(pick)}")
        return pick
    return None


def music_credit(path):
    if not path:
        return None
    name = os.path.basename(path)
    credits_file = os.path.join(ROOT, "assets", "music", "credits.txt")
    if not os.path.exists(credits_file):
        return None
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
    """Pet sounds for each scene (optional, needs ElevenLabs)."""
    PET_SOUNDS = [
        "cute sad meow, isolated, no music, no speech",
        "angry puppy whimper, isolated, no music",
        "happy cat purr, isolated, no music",
        "surprised cat chirp, isolated, no music",
    ]
    out = []
    for i, sc in enumerate(scenes):
        action_text = (sc.get("sfx") or "").strip()
        base_text = PET_SOUNDS[i % len(PET_SOUNDS)]
        path = os.path.join(out_dir, f"sfx_{i}.mp3")

        if action_text and eleven_sound(f"{action_text}, isolated, no music", 1.5, path):
            out.append(path)
        elif eleven_sound(base_text, 1.5, path):
            out.append(path)
        else:
            out.append(None)
    return out
