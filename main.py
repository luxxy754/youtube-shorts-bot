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

try:
    from gradio_client import Client as GradioClient, handle_file
    GRADIO_AVAILABLE = True
except ImportError:
    GradioClient = None
    GRADIO_AVAILABLE = False

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

# IMPORTANT: no broken public Space is hard-coded anymore.
# If you have a working Gradio Wav2Lip Space, set LIPSYNC_SPACES as a comma-separated
# GitHub variable/secret. If it fails, the bot immediately falls back to a normal
# character-video with the voiceover instead of hanging for many minutes.
LIPSYNC_SPACES = [
    s.strip() for s in os.getenv("LIPSYNC_SPACES", "").split(",") if s.strip()
]
LIPSYNC_TIMEOUT_SECONDS = int(os.getenv("LIPSYNC_TIMEOUT_SECONDS", "180"))
ENABLE_LIPSYNC = os.getenv("ENABLE_LIPSYNC", "false").strip().lower() in {"1", "true", "yes", "on"}

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


def try_lipsync(character_image, audio_path):
    if not ENABLE_LIPSYNC:
        print("Lipsync disabled. Using FFmpeg fallback.")
        return None

    if not GRADIO_AVAILABLE:
        print("gradio_client is not installed. Using FFmpeg fallback.")
        return None

    if not LIPSYNC_SPACES:
        print("No LIPSYNC_SPACES configured. Using FFmpeg fallback.")
        return None

    for space in LIPSYNC_SPACES:
        print(f"Trying configured lipsync Space: {space}")
        try:
            client = GradioClient(
                space,
                download_files=str(OUTPUT_DIR / "gradio_downloads"),
            )

            # The old project assumed /generate and parameters named face/audio.
            # We keep that interface because this is what the supplied project used.
            # If the configured Space exposes a different API, the exception is caught
            # and we immediately move to the guaranteed fallback.
            result = client.predict(
                face=handle_file(str(character_image)),
                audio=handle_file(str(audio_path)),
                api_name="/generate",
            )

            local_or_url = extract_file_result(result)
            if not local_or_url:
                print("Lipsync Space returned no file. Trying fallback.")
                continue

            if str(local_or_url).startswith("http"):
                # With download_files enabled the current Gradio client normally
                # materializes output files. If it only returns a URL, download it.
                target = OUTPUT_DIR / f"lipsync_{int(time.time())}.mp4"
                response = requests.get(local_or_url, timeout=LIPSYNC_TIMEOUT_SECONDS)
                response.raise_for_status()
                target.write_bytes(response.content)
                local_or_url = target

            local_path = Path(str(local_or_url))
            if local_path.exists() and local_path.stat().st_size > 10000:
                print(f"Lipsync video received: {local_path}")
                return local_path

            print("Lipsync result path does not exist locally.")
        except Exception as exc:
            print(f"Lipsync Space failed: {exc}")

    print("All configured lipsync Spaces failed. Using FFmpeg fallback immediately.")
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
