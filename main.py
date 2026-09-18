import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import edge_tts
import requests

# Optional dependencies are imported lazily where possible so the bot can still
# create a video when a remote lipsync service is unavailable.
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False


# Wav2Lip is executed locally in the GitHub runner. This avoids unreliable public
# Gradio Spaces returning 403/404 errors.


# ========================= CONFIG =========================
ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

VOICE = os.getenv("EDGE_TTS_VOICE", "hi-IN-SwaraNeural")
RATE = os.getenv("EDGE_TTS_RATE", "+2%")
PITCH = os.getenv("EDGE_TTS_PITCH", "+1Hz")

CHARACTER_IMAGE = ROOT / "character.jpg"
OUTPUT_AUDIO_FILE = OUTPUT_DIR / "voiceover.mp3"
OUTPUT_VIDEO_PATH = OUTPUT_DIR / "short_video.mp4"

YT_PRIVACY_STATUS = os.getenv("YT_PRIVACY_STATUS", "public").strip().lower()
if YT_PRIVACY_STATUS not in {"public", "private", "unlisted"}:
    YT_PRIVACY_STATUS = "public"

WAV2LIP_DIR = Path(os.getenv("WAV2LIP_DIR", ROOT / "third_party" / "Wav2Lip"))
WAV2LIP_CHECKPOINT = Path(os.getenv("WAV2LIP_CHECKPOINT", ROOT / "models" / "wav2lip_gan.pth"))
WAV2LIP_FACE_DET = Path(os.getenv("WAV2LIP_FACE_DET", WAV2LIP_DIR / "face_detection" / "detection" / "sfd" / "s3fd.pth"))
ENABLE_LIPSYNC = os.getenv("ENABLE_LIPSYNC", "true").strip().lower() in {"1", "true", "yes", "on"}
WAV2LIP_BATCH_SIZE = int(os.getenv("WAV2LIP_BATCH_SIZE", "16"))

print("AI Influencer Bot Initialized.")


# ========================= SCRIPT =========================
def fallback_content():
    return (
        "Aajkal AI literally har jagah nazar aa rahi hai. Study se lekar business aur daily work tak "
        "har cheez ke liye naye tools aa rahe hain. Aur honestly sabse interesting baat ye hai ke inmein "
        "se bohat se tools use karna bilkul difficult nahi hai. Bas thoda curious raho aur jo naya tool "
        "dikhe usko try karo. Ho sakta hai jo cheez aaj tum sirf trend samajh rahe ho wahi kal tumhara "
        "favourite tool ban jaye. Comment mein batao tum abhi kaunsa AI tool sabse zyada use kar rahe ho!"
    )


def clean_json_text(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def generate_influencer_script():
    fallback_title = "Aaj Ki Viral Baat! #Shorts"
    fallback_script = fallback_content()

    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY not set. Using fallback content.")
        return fallback_title, fallback_script

    api_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

    instruction = (
        "Generate one short AI-trend YouTube Shorts script. "
        "Use Roman Urdu/Hinglish, casual Pakistani/Indian spoken style, 90-120 words. "
        "It must be one flowing spoken thought, not a list. Avoid difficult Urdu/Hindi words. "
        "Return ONLY valid JSON in this exact format: "
        '{"title":"catchy title","script":"spoken script"}'
    )

    body = {"contents": [{"parts": [{"text": instruction}]}]}

    try:
        print(f"Asking Gemini ({GEMINI_MODEL}) for a script...")
        response = requests.post(api_url, json=body, timeout=60)

        if response.status_code == 429:
            # Quota exhaustion is not a reason to kill the whole pipeline.
            # The official Gemini docs classify this as a rate/quota error.
            print("Gemini returned 429 quota/rate limit. Using fallback content immediately.")
            return fallback_title, fallback_script

        if response.status_code != 200:
            print(f"Gemini returned HTTP {response.status_code}. Using fallback content.")
            return fallback_title, fallback_script

        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(clean_json_text(text))

        title = str(parsed.get("title") or fallback_title).strip()
        script = str(parsed.get("script") or fallback_script).strip()
        return title, script

    except Exception as exc:
        print(f"Gemini failed: {exc}. Using fallback content.")
        return fallback_title, fallback_script


# ========================= TTS =========================
def clean_script_for_speech(text):
    text = re.sub(r"#\w+", "", text)
    text = re.sub(r"[*_~`]", "", text)
    text = re.sub(r"[\U0001F300-\U0001FAFF]", "", text)
    text = re.sub(r"\.{2,}", ".", text)

    # Remove sentence punctuation entirely for TTS. Edge-TTS can create a long
    # sentence-boundary pause on . ? ! ; : and even commas. The Shorts voiceover
    # should sound like one continuous spoken thought. Keep only word spacing.
    text = re.sub(r"[.!?,;:]+", " ", text)
    text = re.sub(r"[-—–]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def generate_edge_tts_async(text, output_path):
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH)
    await communicate.save(str(output_path))


def generate_voiceover(script_text):
    script_text = clean_script_for_speech(script_text)
    print(f"Generating voiceover with Edge-TTS (voice={VOICE})...")
    try:
        asyncio.run(generate_edge_tts_async(script_text, OUTPUT_AUDIO_FILE))
        if OUTPUT_AUDIO_FILE.exists() and OUTPUT_AUDIO_FILE.stat().st_size > 1000:
            print("Voiceover generated successfully.")
            return OUTPUT_AUDIO_FILE
    except Exception as exc:
        print(f"Edge-TTS failed: {exc}")
    return None


# ========================= VIDEO =========================
def run_command(command, timeout=240):
    print("Running:", " ".join(map(str, command)))
    result = subprocess.run(
        [str(x) for x in command],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        print(result.stdout[-6000:])
        raise RuntimeError(f"Command failed with exit code {result.returncode}")
    return result.stdout


def make_fallback_video(image_path, audio_path, output_path):
    """Guaranteed CPU-only video fallback: portrait character + voiceover.

    This intentionally does not fake lip movement. It creates a valid MP4 that can
    be uploaded when no reliable lipsync service is available.
    """
    print("Creating reliable portrait video fallback with FFmpeg...")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1080x1920 portrait. The image is scaled to fill the frame without distortion.
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1"
    )

    command = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "25",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        output_path,
    ]
    run_command(command, timeout=240)

    if not output_path.exists() or output_path.stat().st_size < 10000:
        raise RuntimeError("FFmpeg did not create a valid video file.")

    print(f"Fallback video ready: {output_path}")
    return output_path


def extract_file_result(result):
    """Return a local path or remote URL from common Gradio output shapes."""
    node = result
    while isinstance(node, (list, tuple)) and node:
        node = node[0]

    if isinstance(node, str):
        return node

    if isinstance(node, dict):
        # Gradio FileData usually exposes path/url.
        return node.get("path") or node.get("url") or node.get("name")

    # Newer client FileData-like objects can expose these attributes.
    for attr in ("path", "url", "name"):
        value = getattr(node, attr, None)
        if value:
            return value

    return None


def normalize_lipsync_video(input_path, output_path):
    """Convert the remote lipsync result into a clean 1080x1920 Shorts MP4."""
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1"
    )
    command = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        output_path,
    ]
    run_command(command, timeout=240)
    if not output_path.exists() or output_path.stat().st_size < 10000:
        raise RuntimeError("FFmpeg did not create a valid normalized lipsync video.")
    return output_path


def try_lipsync(character_image, audio_path):
    """Run Wav2Lip locally on the GitHub runner.

    The previous version depended on public Gradio Spaces, which returned 403s.
    Local Wav2Lip is deterministic and does not depend on a Space being awake.
    """
    if not ENABLE_LIPSYNC:
        print("Lipsync disabled. Using FFmpeg fallback.")
        return None

    inference_py = WAV2LIP_DIR / "inference.py"
    if not inference_py.exists():
        print(f"Wav2Lip source not found: {inference_py}")
        return None
    if not WAV2LIP_CHECKPOINT.exists() or WAV2LIP_CHECKPOINT.stat().st_size < 100_000_000:
        print(f"Wav2Lip checkpoint missing or too small: {WAV2LIP_CHECKPOINT}")
        return None
    if not WAV2LIP_FACE_DET.exists() or WAV2LIP_FACE_DET.stat().st_size < 10_000_000:
        print(f"Wav2Lip face detector missing or too small: {WAV2LIP_FACE_DET}")
        return None

    output = OUTPUT_DIR / "wav2lip_result.mp4"
    print("Running LOCAL Wav2Lip lipsync (CPU)...")
    command = [
        sys.executable, str(inference_py),
        "--checkpoint_path", str(WAV2LIP_CHECKPOINT),
        "--face", str(character_image),
        "--audio", str(audio_path),
        "--outfile", str(output),
        "--static",
        "--resize_factor", "2",
        "--nosmooth",
        "--pads", "0", "10", "0", "0",
        "--face_det_batch_size", "4",
        "--wav2lip_batch_size", str(WAV2LIP_BATCH_SIZE),
    ]
    try:
        run_command(command, timeout=1500)
        if not output.exists() or output.stat().st_size < 10000:
            raise RuntimeError("Wav2Lip did not create a usable output video.")
        normalized = OUTPUT_DIR / "lipsync_normalized.mp4"
        normalize_lipsync_video(output, normalized)
        print(f"LOCAL Wav2Lip lipsync ready: {normalized}")
        return normalized
    except Exception as exc:
        print(f"Local Wav2Lip failed: {exc}")
        print("Using FFmpeg fallback immediately.")
        return None


def create_video(character_image, audio_path):
    lipsync_video = try_lipsync(character_image, audio_path)

    if lipsync_video:
        shutil.copy2(lipsync_video, OUTPUT_VIDEO_PATH)
    else:
        make_fallback_video(character_image, audio_path, OUTPUT_VIDEO_PATH)

    return OUTPUT_VIDEO_PATH


# ========================= YOUTUBE =========================
def upload_to_youtube(video_path, title):
    client_id = os.getenv("YT_CLIENT_ID", "").strip()
    client_secret = os.getenv("YT_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("YT_REFRESH_TOKEN", "").strip()

    if not YOUTUBE_AVAILABLE:
        raise RuntimeError("YouTube Python dependencies are not installed.")

    if not client_id or not client_secret or not refresh_token:
        raise RuntimeError(
            "Missing YT_CLIENT_ID, YT_CLIENT_SECRET, or YT_REFRESH_TOKEN GitHub secret."
        )

    video_path = Path(video_path)
    if not video_path.exists() or video_path.stat().st_size < 10000:
        raise RuntimeError(f"Invalid video file: {video_path}")

    print("Authenticating with YouTube...")
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )

    # Force the refresh now so an invalid/mismatched refresh token fails here,
    # before the upload request starts.
    credentials.refresh(Request())
    print("YouTube OAuth refresh succeeded.")

    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)

    body = {
        "snippet": {
            "title": title[:100],
            "description": "Generated automatically via AI Influencer Bot #Shorts",
            "tags": ["AI", "Shorts", "Trending"],
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": YT_PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,
        },
    }

    print(f"Uploading video to YouTube with privacyStatus={YT_PRIVACY_STATUS}...")
    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        chunksize=8 * 1024 * 1024,
        resumable=True,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"YouTube upload progress: {int(status.progress() * 100)}%")

    video_id = response.get("id")
    if not video_id:
        raise RuntimeError(f"YouTube returned no video ID: {response}")

    # The insert response itself is enough to confirm the upload request returned
    # a YouTube video ID. Avoid an extra API call because it can require scopes
    # beyond youtube.upload.
    print(f"YouTube upload complete: https://www.youtube.com/watch?v={video_id}")

    return video_id


# ========================= MAIN =========================
def main():
    title, script_text = generate_influencer_script()
    print(f"Title: {title}")
    print(f"Script: {script_text}")

    audio_file = generate_voiceover(script_text)
    if not audio_file:
        raise RuntimeError("Voiceover generation failed.")

    if not CHARACTER_IMAGE.exists():
        raise RuntimeError(f"character.jpg not found at {CHARACTER_IMAGE}")

    video_file = create_video(CHARACTER_IMAGE, audio_file)
    print(f"Final video ready: {video_file}")

    # Do not silently swallow YouTube errors. If upload fails, GitHub Actions must
    # become red so the real reason is visible in the run log.
    video_id = upload_to_youtube(video_file, title)
    print(f"SUCCESS: YouTube video uploaded. ID={video_id}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\n========== PIPELINE FAILED ==========")
        print(str(exc))
        raise
