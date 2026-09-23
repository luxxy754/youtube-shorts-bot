"""Audio: Hindi/Urdu dialogue via edge-tts."""
import asyncio
import glob
import hashlib
import os
import random
import subprocess

import edge_tts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VOICE_MAP = {
    "hi": {"female": "hi-IN-SwaraNeural", "male": "hi-IN-MadhurNeural"},
    "ur": {"female": "ur-PK-UzmaNeural",   "male": "ur-PK-AsadNeural"},
}
DEFAULT_LANG   = os.getenv("TTS_LANG", "hi")
DEFAULT_GENDER = os.getenv("TTS_GENDER", "female")
DEFAULT_RATE   = os.getenv("TTS_RATE", "-8%")
DEFAULT_PITCH  = os.getenv("TTS_PITCH", "+2Hz")


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


def eleven_dialogue(text, path, voice_id=None):
    if not text.strip():
        return False
    cache_key = hashlib.md5(f"{text}|{voice_id}".encode()).hexdigest()
    cache_path = os.path.join(_cache_dir(), f"{cache_key}.mp3")
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
        with open(cache_path, "rb") as src, open(path, "wb") as dst:
            dst.write(src.read())
        return True
    voice = voice_id or _voice_id()
    try:
        asyncio.run(_tts_save(text, voice, DEFAULT_RATE, DEFAULT_PITCH, path))
    except Exception as exc:
        print(f"  edge-tts err: {str(exc)[:200]}")
        try:
            asyncio.run(_tts_save(text, VOICE_MAP["hi"]["male"],
                                   DEFAULT_RATE, DEFAULT_PITCH, path))
        except Exception:
            return False
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        with open(cache_path, "wb") as f:
            with open(path, "rb") as src:
                f.write(src.read())
        print(f"  Dialogue OK ({os.path.getsize(path)//1024} KB)")
        return True
    return False


def _keys():
    return [os.getenv(f"ELEVEN_KEY_{i}", "").strip() for i in (1, 2, 3) if os.getenv(f"ELEVEN_KEY_{i}", "").strip()]


def eleven_sound(text, seconds, path):
    keys = _keys()
    if not keys:
        return False
    import requests
    for key in keys:
        try:
            r = requests.post(
                "https://api.elevenlabs.io/v1/sound-generation",
                headers={"xi-api-key": key},
                json={"text": text, "duration_seconds": seconds,
                      "prompt_influence": 0.6}, timeout=120)
            if r.status_code == 200 and r.content:
                with open(path, "wb") as f:
                    f.write(r.content)
                return True
        except Exception:
            continue
    return False


def eleven_music(prompt, seconds, path):
    keys = _keys()
    if not keys:
        return False
    import requests
    ms = max(3000, min(int(seconds * 1000), 600000))
    for key in keys:
        try:
            r = requests.post(
                "https://api.elevenlabs.io/v1/music",
                headers={"xi-api-key": key, "Accept": "audio/mpeg"},
                json={"prompt": prompt, "music_length_ms": ms,
                      "model_id": "music_v2"}, timeout=300)
            if r.status_code == 200 and r.content and len(r.content) > 5000:
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
    own += glob.glob(os.path.join(ROOT, "*.mp3"))
    good = [p for p in own if _valid_audio(p)]
    if good:
        return random.choice(good)
    full = f"{prompt}. Instrumental only, no vocals, no singing."
    if eleven_music(full, seconds, path):
        return path
    return None


def music_credit(path):
    if not path:
        return None
    name = os.path.basename(path)
    for credits_file in (os.path.join(ROOT, "assets", "music", "credits.txt"),
                         os.path.join(ROOT
