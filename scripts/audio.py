"""Audio: Hindi/Urdu dialogue TTS via edge-tts + SFX + music.

edge-tts = Microsoft Neural TTS, free, no API key.
Native Hindi (hi-IN) and Urdu (ur-PK) voices.
More natural than most paid TTS for Hindi/Urdu.
"""
import asyncio
import glob
import hashlib
import os
import random
import subprocess

import edge_tts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- Native Hindi/Urdu voices ----
VOICE_MAP = {
    "hi": {
        "female": "hi-IN-SwaraNeural",   # Warm Hindi female - best for kids
        "male":   "hi-IN-MadhurNeural",  # Clear Hindi male
    },
    "ur": {
        "female": "ur-PK-UzmaNeural",    # Native Urdu female
        "male":   "ur-PK-AsadNeural",    # Native Urdu male
    },
}

DEFAULT_LANG   = os.getenv("TTS_LANG", "hi")       # "hi" or "ur"
DEFAULT_GENDER = os.getenv("TTS_GENDER", "female")  # "female" or "male"
DEFAULT_RATE   = os.getenv("TTS_RATE", "-8%")       # slower = natural for kids
DEFAULT_PITCH  = os.getenv("TTS_PITCH", "+2Hz")


def _cache_dir():
    d = os.path.join(ROOT, "output", "audio_cache")
    os.makedirs(d, exist_ok=True)
    return d


def _voice_id(lang=None, gender=None):
    lang   = lang   or DEFAULT_LANG
    gender = gender or DEFAULT_GENDER
    return VOICE_MAP.get(lang, VOICE_MAP["hi"]).get(gender, VOICE_MAP["hi"]["female"])


async def _tts_save(text, voice, rate, pitch, out_path):
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(out_path)


def eleven_dialogue(text, path, voice_id=None):
    """Generate Hindi/Urdu speech via edge-tts.

    Name kept as 'eleven_dialogue' so main.py doesn't need changes.
    """
    if not text.strip():
        return False

    # Cache
    cache_key  = hashlib.md5(f"{text}|{voice_id}".encode()).hexdigest()
    cache_path = os.path.join(_cache_dir(), f"{cache_key}.mp3")
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
        with open(cache_path, "rb") as src, open(path, "wb") as dst:
            dst.write(src.read())
        print(f"  Dialogue cache hit: {text[:40]}...")
        return True

    voice = voice_id or _voice_id()

    try:
        asyncio.run(_tts_save(text, voice, DEFAULT_RATE, DEFAULT_PITCH, path))
    except Exception as exc:
        print(f"  edge-tts error: {str(exc)[:200]}")
        # Fallback to Hindi male
        try:
            fallback = VOICE_MAP["hi"]["male"]
            asyncio.run(_tts_save(text, fallback, DEFAULT_RATE, DEFAULT_PITCH, path))
        except Exception as exc2:
            print(f"  Fallback failed: {str(exc2)[:200]}")
            return False

    if os.path.exists(path) and os.path.getsize(path) > 1000:
        with open(cache_path, "wb") as f:
            with open(path, "rb") as src:
                f.write(src.read())
        print(f"  Dialogue OK ({os.path.getsize(path)//1024} KB) voice={voice}")
        return True

    print(f"  edge-tts output missing/small")
    return False


# ---- SFX + Music: ElevenLabs optional (agar keys na hon to skip) ----
def _keys():
    ks = [os.getenv(f"ELEVEN_KEY_{i}", "").strip() for i in (1, 2, 3)]
    return [k for k in ks if k]


def eleven_sound(text, seconds, path):
    """Optional SFX via ElevenLabs. Skips if no keys."""
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
                      "prompt_influence": 0.6},
                timeout=120)
            if r.status_code == 200 and r.content:
                with open(path, "wb") as f:
                    f.write(r.content)
                return True
        except Exception:
            continue
    return False


def eleven_music(prompt, seconds, path):
    """Optional music via ElevenLabs. Skips if no keys."""
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
                      "model_id": "music_v2"},
                timeout=300)
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
    # Local mp3 first (best option)
    own = glob.glob(os.path.join(ROOT, "assets", "music", "*.mp3"))
    own += glob.glob(os.path.join(ROOT, "*.mp3"))
    good = [p for p in own if _valid_audio(p)]
    if good:
        pick = random.choice(good)
        print(f"  Using own music: {os.path.basename(pick)}")
        return pick

    # Try ElevenLabs (agar key ho)
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
    """Optional SFX. Agar ElevenLabs key nahi to sab None."""
    SFX_SOUNDS = [
        "a short cute cartoon pop, isolated, no music",
        "a soft happy cartoon sparkle chime, isolated, no music",
        "a playful cartoon boing, isolated, no music",
    ]
    out = []
    for i, sc in enumerate(scenes):
        action_text = (sc.get("sfx") or "").strip()
        base_text = SFX_SOUNDS[i % len(SFX_SOUNDS)]
        base_path = os.path.join(out_dir, f"sfx_{i}_primary.mp3")
        parts = [base_path] if eleven_sound(base_text, 1.5, base_path) else []
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
        except Exception as exc:
            print(f"  sfx mix failed: {str(exc)[:150]}")
            out.append(parts[0])
    return out
