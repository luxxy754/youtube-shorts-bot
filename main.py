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
# Public free Wav2Lip Spaces (lips-only movement, no head/body movement - matches
# "sirf lipsync, koi aur movement nahi" requirement). Comma-separated override via
# LIPSYNC_SPACES env var if you ever want to add/replace one.
DEFAULT_LIPSYNC_SPACES = "manavisrani07/gradio-lipsync-wav2lip,Artificial-superintelligence/gradio-lipsync-wav2lip"
LIPSYNC_SPACES = [s.strip() for s in os.getenv("LIPSYNC_SPACES", DEFAULT_LIPSYNC_SPACES).split(",") if s.strip()]
LIPSYNC_CHECKPOINT = os.getenv("LIPSYNC_CHECKPOINT", "wav2lip")  # or "wav2lip_gan" (slower, sharper mouth)
LIPSYNC_TIMEOUT_SECONDS = int(os.getenv("LIPSYNC_TIMEOUT_SECONDS", "420"))

# Self-hosted Wav2Lip fallback: runs directly on the Actions runner (CPU), so it
# never depends on a third-party Space being online. Heavier (bigger download,
# slower per run) but guaranteed to actually attempt lipsync every time.
WAV2LIP_ENGINE_DIR = "wav2lip_engine"
WAV2LIP_ENGINE_REPO = os.getenv("WAV2LIP_ENGINE_REPO", "camenduru/Wav2Lip")
# IMPORTANT: "checkpoints/wav2lip.pth" in this HF repo is a broken/corrupted upload -
# it's only ~167KB (a real checkpoint is well over 100MB), so torch.load on it either
# crashes or produces garbage, and every self-hosted run was silently failing and
# falling through to the static-image fallback (no lipsync at all). "wav2lip_gan.pth"
# in the same repo is a valid, full-size (~436MB) checkpoint, so that's now the
# default - it also tends to give sharper mouth shapes than the plain model anyway.
WAV2LIP_SELFHOSTED_CHECKPOINT = os.getenv("WAV2LIP_SELFHOSTED_CHECKPOINT", "wav2lip_gan.pth")
WAV2LIP_INFERENCE_TIMEOUT = int(os.getenv("WAV2LIP_INFERENCE_TIMEOUT", "900"))

YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN", "")
YT_PRIVACY_STATUS = os.getenv("YT_PRIVACY_STATUS", "public")

CHARACTER_IMAGE = "character.jpg"

print("AI Influencer Bot Initialized with Edge-TTS.")


def generate_influencer_script():
    """Gemini se aajkal ke trending topics par Hinglish script generate karwata hai.
    ~90-130 words rakhte hain taake normal bolne ki speed par final Short 30-40
    second ka bane (bahut chhota script = bahut chhota video)."""
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
    """Asynchronous helper to generate audio using edge-tts."""
    communicate = edge_tts.Communicate(script_text, VOICE, rate=RATE, pitch=PITCH)
    await communicate.save(output_path)


def generate_voiceover(script_text):
    """Edge-TTS ka use karke natural sounding voiceover banata hai with configured speed and pitch."""
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
    """Free Hugging Face Wav2Lip Space se sirf LIPS move karta hua video banata hai
    (koi head/body movement nahi - bilkul static photo, bas mooh audio ke sath sync).
    Agar sab Spaces fail ho jayein (busy/queued/down), None return karta hai taake
    caller static (no-lipsync) video par fallback kar sake."""
    if not GRADIO_AVAILABLE:
        print("gradio_client not installed - skipping lipsync step.")
        return None

    def make_client(space, token):
        """These Spaces are public, so token is optional (only helps avoid shared
        rate limits). Different gradio_client versions use different keyword names
        for it (hf_token vs token), so try both, then fall back to no token at all
        rather than crashing the whole run over a library version mismatch."""
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
    attempts = tokens + [None]  # always keep a no-token attempt as a last resort

    for space in LIPSYNC_SPACES:
        for token_idx, token in enumerate(attempts):
            try:
                label = f"{space} (token {token_idx + 1})" if token else f"{space} (no token)"
                print(f"Trying lipsync via Hugging Face Space: {label} ...")
                client = make_client(space, token)

                job = client.submit(
                    handle_file(character_image),  # face image
                    handle_file(audio_path),        # driving audio
                    LIPSYNC_CHECKPOINT,             # "wav2lip" or "wav2lip_gan"
                    False,                          # no_smooth
                    1,                              # resize_factor
                    0,                              # pad_top
                    10,                             # pad_bottom
                    0,                              # pad_left
                    0,                              # pad_right
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
    """Wav2Lip code + checkpoints (~1GB) ko ek hi baar download karta hai (agli baar
    actions/cache se turant mil jayega). camenduru/Wav2Lip HF repo mein poora ready-
    to-run Wav2Lip already sahi folder structure mein bundled hai (code, s3fd face
    detector, checkpoints) - isliye alag alag jagah se cheezein jodne ki zaroorat
    nahi padti."""
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
    """Wav2Lip ko seedha Actions runner (CPU) par chalata hai - koi third-party
    Space/API par depend nahi karta, isliye sabse reliable option hai. Dheema hai
    (CPU par kuch minute lag sakte hain) par lipsync guarantee karta hai."""
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
    ]

    try:
        print("Running self-hosted Wav2Lip inference (can take a few minutes on CPU)...")
        result = subprocess.run(
            cmd, cwd=engine_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=WAV2LIP_INFERENCE_TIMEOUT,
        )
        if result.returncode != 0 or not os.path.exists(out_path):
            tail = result.stderr.decode("utf-8", errors="ignore")[-2500:]
            print(f"Self-hosted Wav2Lip failed:\n{tail}")
            return None
        print("Self-hosted Wav2Lip succeeded.")
        return out_path
    except subprocess.TimeoutExpired:
        print(f"Self-hosted Wav2Lip timed out after {WAV2LIP_INFERENCE_TIMEOUT}s.")
        return None
    except Exception as e:
        print(f"Self-hosted Wav2Lip crashed: {e}")
        return None


def create_static_influencer_video(character_image, audio_path):
    """Fallback: fixed character image par bina movement/lipsync ke audio merge
    karke video banata hai. Sirf tab use hota hai jab lipsync step fail ho jaye,
    taake daily upload kabhi na ruke."""
    video_file = "scene_video.mp4"

    if not os.path.exists(character_image):
        print(f"Error: {character_image} not found in repository!")
        return None

    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", character_image,
        "-i", audio_path,
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", video_file,
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0 or not os.path.exists(video_file):
        print(f"FFmpeg error: {result.stderr.decode('utf-8')}")
        return None

    return video_file


def finalize_video(raw_video_path):
    """Lipsync/static video ko 1080x1920 (Shorts) format mein re-encode karta hai
    taake dono paths se aane wala output hamesha same, upload-ready shape mein ho."""
    final_path = "final_short.mp4"
    cmd = [
        "ffmpeg", "-y", "-i", raw_video_path,
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
        final_path,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0 or not os.path.exists(final_path):
        print(f"Final re-encode failed, using raw file as-is: {result.stderr.decode('utf-8')}")
        return raw_video_path
    return final_path


def upload_to_youtube(video_path, title, description, tags=None):
    """YouTube auto-upload function."""
    if not YOUTUBE_AVAILABLE:
        print("YouTube libraries not available.")
        return None

    if not (YT_CLIENT_ID and YT_CLIENT_SECRET and YT_REFRESH_TOKEN):
        print("YouTube credentials missing in GitHub Secrets! Please check YT_CLIENT_ID, YT_CLIENT_SECRET, and YT_REFRESH_TOKEN.")
        return None

    try:
        creds = Credentials(
            token=None, refresh_token=YT_REFRESH_TOKEN,
            client_id=YT_CLIENT_ID, client_secret=YT_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        youtube = build("youtube", "v3", credentials=creds)
        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": tags or ["AI", "Shorts", "Influencer", "Hinglish"],
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": YT_PRIVACY_STATUS,
                "selfDeclaredMadeForKids": False,
            },
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()

        video_id = response.get("id")
        print(f"Successfully uploaded to YouTube! Video ID: {video_id}")
        return video_id
    except Exception as e:
        print(f"YouTube upload failed completely: {e}")
        return None


def main():
    title, script = generate_influencer_script()
    print(f"Title: {title}")
    print(f"Script: {script}")
    print(f"Script length: {len(script)} characters")

    audio_path = generate_voiceover(script)
    if not audio_path:
        sys.exit(1)

    raw_video = generate_lipsync_video(CHARACTER_IMAGE, audio_path)
    if not raw_video:
        raw_video = generate_lipsync_video_selfhosted(CHARACTER_IMAGE, audio_path)
    if not raw_video:
        print("Lipsync fully unavailable this run - using static image as last resort.")
        raw_video = create_static_influencer_video(CHARACTER_IMAGE, audio_path)
    if not raw_video:
        sys.exit(1)

    final_video = finalize_video(raw_video)

    video_description = f"{title}\n\n#Shorts #AIInfluencer #Trending #Hinglish"
    upload_to_youtube(final_video, f"{title} #Shorts", video_description)


if __name__ == "__main__":
    main()
