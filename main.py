import asyncio
import edge_tts
import json
import os
import requests
import sys
import time
import traceback

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

# --- TTS Configuration ---
VOICE = os.getenv("EDGE_TTS_VOICE", "hi-IN-SwaraNeural")
RATE = os.getenv("EDGE_TTS_RATE", "-5%")
PITCH = os.getenv("EDGE_TTS_PITCH", "-4Hz")
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

CHARACTER_IMAGE = "character.jpg"
OUTPUT_VIDEO_PATH = "output/short_video.mp4"

print("AI Influencer Bot Initialized with Edge-TTS.")


def generate_influencer_script():
    fallback_title = "Aaj Ki Viral Baat! #Shorts"
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
        "English words the way young speakers actually talk. Keep sentences short and natural. "
        "The script MUST take roughly 30-40 seconds to speak — about 90 to 130 words. "
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
    print(f"Generating voiceover with Edge-TTS (voice={VOICE})...")
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
            except Exception as e:
                print(f"Lipsync attempt failed on {space} (token {token_idx + 1}): {e}")
                traceback.print_exc()
                time.sleep(5)  # chhota sa gap, taake Space ko cool-down / queue clear karne ka mauka mile
                continue

    print("All Hugging Face Space attempts for lipsync failed.")
    return None


def upload_to_youtube(video_path, title):
    if not YOUTUBE_AVAILABLE:
        print("YouTube libraries not available - skipping upload.")
        return

    client_id = os.getenv("YT_CLIENT_ID", "")
    client_secret = os.getenv("YT_CLIENT_SECRET", "")
    refresh_token = os.getenv("YT_REFRESH_TOKEN", "")

    if not client_id or not client_secret or not refresh_token:
        print("YouTube credentials missing - skipping upload.")
        return

    try:
        print("Uploading video to YouTube Shorts...")
        creds = Credentials(
            None,
            refresh_token=refresh_token,
            token_uri="[https://oauth2.googleapis.com/token](https://oauth2.googleapis.com/token)",
            client_id=client_id,
            client_secret=client_secret,
        )
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title,
                "description": "Generated automatically via AI Pipeline #Shorts",
                "tags": ["AI", "Shorts", "Tech"],
                "categoryId": "28"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%.")

        print(f"Video uploaded successfully! ID: {response.get('id')}")
    except Exception as e:
        print(f"YouTube upload failed: {e}")


def main():
    os.makedirs("output", exist_ok=True)
    
    # Step 1: Generate Script
    title, script_text = generate_influencer_script()
    print(f"Title: {title}")
    print(f"Script: {script_text}")

    # Step 2: Generate Voiceover
    audio_file = generate_voiceover(script_text)
    if not audio_file:
        print("Critical Error: Voiceover generation failed.")
        return

    # Step 3: Generate Lipsync Video
    if not os.path.exists(CHARACTER_IMAGE):
        print(f"Error: {CHARACTER_IMAGE} not found in repository root!")
        return

    video_output = generate_lipsync_video(CHARACTER_IMAGE, audio_file)
    lipsync_succeeded = bool(video_output and os.path.exists(video_output))

    if lipsync_succeeded:
        import shutil
        shutil.copy(video_output, OUTPUT_VIDEO_PATH)
        print(f"Final video ready at: {OUTPUT_VIDEO_PATH}")
    else:
        # Pehle yahan seedha ek silent black video ban ke YouTube pe upload ho jata tha.
        # Ab hum wo broken video YouTube pe post NHI karenge - sirf local debug ke liye bana rahe hain.
        print("Lipsync failed on all Spaces. Saving a local placeholder for debugging (NOT uploading it)...")
        os.system(f'ffmpeg -y -f lavfi -i color=c=black:s=1080x1920:d=15 -c:v libx264 {OUTPUT_VIDEO_PATH}')
        print("Critical Error: Real lipsync video nahi ban saka, isliye YouTube upload skip kiya ja raha hai.")
        print("Tip: GitHub Actions logs mein 'Lipsync attempt failed on ...' lines dekhein for exact reason.")
        return

    # Step 4: Upload to YouTube (sirf tab jab asal lipsync video ban chuka ho)
    upload_to_youtube(OUTPUT_VIDEO_PATH, title)


if __name__ == "__main__":
    main()
