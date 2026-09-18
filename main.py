import asyncio
import edge_tts
import json
import os
import requests
import subprocess
import sys

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False

try:
    from gradio_client import Client as GradioClient
    try:
        from gradio_client import handle_file
    except ImportError:
        def handle_file(path):
            return path
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False

try:
    from huggingface_hub import snapshot_download
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False

# ==================== CONFIGURATION ====================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# --- TTS Configuration (Updated for natural tone, speed, and pitch) ---
VOICE = os.getenv("EDGE_TTS_VOICE", "hi-IN-SwaraNeural")  # Hindi (India) voice — matches Hinglish script accent
RATE = os.getenv("EDGE_TTS_RATE", "-5%")                 # Slightly slows down speech speed
PITCH = os.getenv("EDGE_TTS_PITCH", "-4Hz")              # Lowers pitch to remove thin, robotic sharpness
OUTPUT_AUDIO_FILE = "voiceover.mp3"

HF_KEYS = [
    os.getenv("HF_TOKEN", ""),
    os.getenv("HF_TOKEN_2", ""),
    os.getenv("HF_TOKEN_3", ""),
]

DEFAULT_LIPSYNC_SPACES = "manavisrani07/gradio-lipsync-wav2lip,Artificial-superintelligence/gradio-lipsync-wav2lip"
LIPSYNC_SPACES = [s.strip() for s in os.getenv("LIPSYNC_SPACES", DEFAULT_LIPSYNC_SPACES).split(",") if s.strip()]
LIPSYNC_CHECKPOINT = os.getenv("LIPSYNC_CHECKPOINT", "wav2lip")  
LIPSYNC_TIMEOUT_SECONDS = int(os.getenv("LIPSYNC_TIMEOUT_SECONDS", "420"))

WAV2LIP_ENGINE_DIR = "wav2lip_engine"
WAV2LIP_ENGINE_REPO = os.getenv("WAV2LIP_ENGINE_REPO", "camenduru/Wav2Lip")
WAV2LIP_SELFHOSTED_CHECKPOINT = os.getenv("WAV2LIP_SELFHOSTED_CHECKPOINT", "wav2lip_gan.pth")
WAV2LIP_INFERENCE_TIMEOUT = int(os.getenv("WAV2LIP_INFERENCE_TIMEOUT", "900"))

YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN", "")
YT_PRIVACY_STATUS = os.getenv("YT_PRIVACY_STATUS", "public")

# --- Caption Configuration (Groq Whisper - free, fast speech-to-text) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3")
ENABLE_CAPTIONS = os.getenv("ENABLE_CAPTIONS", "true").lower() == "true"
CAPTION_WORDS_PER_CHUNK = int(os.getenv("CAPTION_WORDS_PER_CHUNK", "3"))

CHARACTER_IMAGE = "character.jpg"

print("AI Influencer Bot Initialized with Edge-TTS.")


def generate_influencer_script():
    fallback_title = "Aaj Ki Viral Baat!"
    fallback_script = (
        "Dosto, kya aapko pata hai aajkal technology ki duniya mein kya naya chal raha hai? "
        "AI itni tez raftar se aage badh rahi hai ke har hafte ek naya breakthrough saamne aata hai. "
        "Chaho social media ho, chaho education ya business, har jagah smart tools cheezein aasan bana rahe hain. "
        "Bas thoda curious raho aur naye trends ko explore karte raho, kyunke jo aaj seekhoge wahi kal kaam aayega. "
        "Mujhe comment mein batao aapko kaunsa AI tool sabse zyada pasand hai!"
    )

    if not GEMINI_API_KEY:
        print("No GEMINI_API_KEY set - using fallback script.")
        return fallback_title, fallback_script

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    instruction = (
        "Generate a trending script for an AI influencer YouTube Short. Write it in natural spoken "
        "Hindi/Urdu (Hinglish), written in Roman/Latin script, with a light, natural mix of common "
        "English words the way young Indian/Pakistani speakers actually talk - not a heavy or forced "
        "mix. This script will be read aloud by a text-to-speech voice, so: use standard, common "
        "Hinglish spellings for Hindi/Urdu words (the kind people normally type on WhatsApp/Instagram), "
        "keep English words spelled correctly in normal English spelling (do not phonetically mangle "
        "them), avoid rare/invented words, and avoid tongue-twisters or awkward consonant clusters that "
        "are hard for a TTS engine to pronounce cleanly. Keep sentences short and natural. "
        "The script MUST take roughly 30-40 seconds to speak at a normal conversational pace - that "
        "means about 90 to 130 words, not shorter. Make it engaging and punchy, with a hook in the "
        "first line and a light call-to-action at the end (like asking to comment or follow). "
        "Reply ONLY with valid JSON, no markdown, no code fences, in this exact shape: "
        '{"title": "catchy title", "script": "Hinglish voiceover script"}'
    )
    body = {"contents": [{"parts": [{"text": instruction}]}]}

    try:
        print("Asking Gemini for trending influencer script...")
        resp = requests.post(api_url, json=body, timeout=60)
        if resp.status_code != 200:
            print(f"Gemini API returned status code {resp.status_code}: {resp.text}")
            return fallback_title, fallback_script

        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()

        parsed = json.loads(text)
        return (
            str(parsed.get("title") or fallback_title).strip(),
            str(parsed.get("script") or fallback_script).strip(),
        )
    except Exception as e:
        print(f"Gemini error: {e}. Using fallbacks.")
        return fallback_title, fallback_script


async def _generate_edge_tts_async(script_text, output_path):
    communicate = edge_tts.Communicate(script_text, VOICE, rate=RATE, pitch=PITCH)
    await communicate.save(output_path)


def generate_voiceover(script_text):
    print(f"Generating voiceover with Edge-TTS (voice={VOICE}, rate={RATE}, pitch={PITCH})...")
    try:
        asyncio.run(_generate_edge_tts_async(script_text, OUTPUT_AUDIO_FILE))
        if os.path.exists(OUTPUT_AUDIO_FILE):
            print("Successfully generated voiceover using Edge-TTS!")
            return OUTPUT_AUDIO_FILE
        else:
            print("Edge-TTS failed to produce the audio file.")
            return None
    except Exception as e:
        print(f"Edge-TTS generation failed: {e}")
        return None


def generate_lipsync_video(character_image, audio_path):
    if not GRADIO_AVAILABLE:
        print("gradio_client not installed - skipping lipsync step.")
        return None

    def make_client(space, token):
        if not token:
            return GradioClient(space)
        try:
            return GradioClient(space, hf_token=token)
        except TypeError:
            try:
                return GradioClient(space, token=token)
            except TypeError:
                print("This gradio_client version doesn't accept a token kwarg - continuing without one.")
                return GradioClient(space)

    tokens = [t for t in HF_KEYS if t.strip()]
    attempts = tokens + [None]

    for space in LIPSYNC_SPACES:
        for token_idx, token in enumerate(attempts):
            try:
                label = f"{space} (token {token_idx + 1})" if token else f"{space} (no token)"
                print(f"Trying lipsync via Hugging Face Space: {label} ...")
                client = make_client(space, token)

                job = client.submit(
                    handle_file(character_image),
                    handle_file(audio_path),
                    LIPSYNC_CHECKPOINT,
                    False,
                    1,
                    0,
                    10,
                    0,
                    0,
                    api_name="/generate",
                )
                result = job.result(timeout=LIPSYNC_TIMEOUT_SECONDS)

                out_path = None
                if isinstance(result, str):
                    out_path = result
                elif isinstance(result, dict):
                    out_path = result.get("video") or result.get("path") or result.get("name")
                elif isinstance(result, (list, tuple)) and result:
                    first = result[0]
                    out_path = first.get("video") if isinstance(first, dict) else first

                if out_path and os.path.exists(out_path):
                    print(f"Lipsync video generated successfully via {space}")
                    return out_path
                print(f"Lipsync call on {space} returned no usable file: {result}")
            except Exception as e:
                print(f"Lipsync attempt failed on {space}: {e}")
                continue

    print("Free Hugging Face Space attempts failed - will try self-hosted lipsync next.")
    return None


def ensure_wav2lip_engine():
    inference_script = os.path.join(WAV2LIP_ENGINE_DIR, "inference.py")
    if os.path.exists(inference_script):
        return WAV2LIP_ENGINE_DIR

    if not HF_HUB_AVAILABLE:
        print("huggingface_hub not installed - can't download self-hosted Wav2Lip engine.")
        return None

    try:
        print(f"Downloading self-hosted Wav2Lip engine from {WAV2LIP_ENGINE_REPO} (one-time, ~1GB)...")
        snapshot_download(repo_id=WAV2LIP_ENGINE_REPO, local_dir=WAV2LIP_ENGINE_DIR)
        if os.path.exists(inference_script):
            return WAV2LIP_ENGINE_DIR
        print("Download finished but inference.py not found - engine layout unexpected.")
        return None
    except Exception as e:
        print(f"Failed to download self-hosted Wav2Lip engine: {e}")
        return None


def generate_lipsync_video_selfhosted(character_image, audio_path):
    engine_dir = ensure_wav2lip_engine()
    if not engine_dir:
        return None

    checkpoint_path = os.path.join(engine_dir, "checkpoints", WAV2LIP_SELFHOSTED_CHECKPOINT)
    if not os.path.exists(checkpoint_path):
        print(f"Self-hosted checkpoint not found at {checkpoint_path} - skipping.")
        return None

    out_path = os.path.abspath("lipsync_selfhosted.mp4")
    cmd = [
        sys.executable, "inference.py",
        "--checkpoint_path", os.path.join("checkpoints", WAV2LIP_SELFHOSTED_CHECKPOINT),
        "--face", os.path.abspath(character_image),
        "--audio", os.path.abspath(audio_path),
        "--outfile", out_path,
        "--pads", "0", "20", "0", "0",
        "--resize_factor", "1",
