import os
import sys
import json
import requests
import subprocess

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

# ==================== CONFIGURATION ====================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

ELEVEN_KEYS = [
    os.getenv("ELEVEN_KEY_1", ""),
    os.getenv("ELEVEN_KEY_2", ""),
    os.getenv("ELEVEN_KEY_3", ""),
]
ELEVEN_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

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

YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN", "")
YT_PRIVACY_STATUS = os.getenv("YT_PRIVACY_STATUS", "public")

CHARACTER_IMAGE = "character.jpg"

print("AI Influencer Bot Initialized.")


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
        "Generate a trending script for an AI influencer YouTube Short in Hinglish (Hindi/Urdu mixed "
        "naturally with cool English words). The script will be read aloud and MUST take roughly "
        "30-40 seconds to speak at a normal conversational pace - that means about 90 to 130 words, "
        "not shorter. Make it engaging, punchy and conversational, with a hook in the first line and "
        "a light call-to-action at the end (like asking to comment or follow). "
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


def generate_voiceover(script_text):
    """ElevenLabs Free Tier API use karke voice banata hai, with gTTS fallback."""
    audio_path = "voiceover.mp3"
    active_keys = [k for k in ELEVEN_KEYS if k.strip()]

    success = False
    if active_keys:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE_ID}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        payload = {
            "text": script_text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        for idx, key in enumerate(active_keys):
            headers["xi-api-key"] = key
            try:
                print(f"Trying ElevenLabs API with key index {idx + 1}...")
                response = requests.post(url, json=payload, headers=headers, timeout=60)
                if response.status_code == 200:
                    with open(audio_path, "wb") as f:
                        f.write(response.content)
                    print("Successfully generated voiceover using ElevenLabs!")
                    success = True
                    break
                else:
                    print(f"ElevenLabs key {idx + 1} failed with status {response.status_code}: {response.text}")
            except Exception as e:
                print(f"ElevenLabs request error with key {idx + 1}: {e}")
    else:
        print("No ELEVEN_KEY_* found in environment - skipping ElevenLabs.")

    if not success:
        print("Falling back to gTTS for voiceover generation...")
        try:
            from gtts import gTTS
            tts = gTTS(text=script_text, lang="hi", slow=False)
            tts.save(audio_path)
            success = True
        except Exception as e:
            print(f"gTTS fallback also failed: {e}")
            return None

    return audio_path if success else None


def generate_lipsync_video(character_image, audio_path):
    """Free Hugging Face Wav2Lip Space se sirf LIPS move karta hua video banata hai
    (koi head/body movement nahi - bilkul static photo, bas mooh audio ke sath sync).
    Agar sab Spaces fail ho jayein (busy/queued/down), None return karta hai taake
    caller static (no-lipsync) video par fallback kar sake."""
    if not GRADIO_AVAILABLE:
        print("gradio_client not installed - skipping lipsync step.")
        return None

    tokens = [t for t in HF_KEYS if t.strip()] or [None]

    for space in LIPSYNC_SPACES:
        for token_idx, token in enumerate(tokens):
            try:
                label = f"{space} (token {token_idx + 1})" if token else space
                print(f"Trying lipsync via Hugging Face Space: {label} ...")
                client = GradioClient(space, hf_token=token) if token else GradioClient(space)

                job = client.submit(
                    handle_file(character_image),  # face image
                    handle_file(audio_path),        # driving audio
                    LIPSYNC_CHECKPOINT,              # "wav2lip" or "wav2lip_gan"
                    False,                            # no_smooth
                    1,                                 # resize_factor
                    0,                                  # pad_top
                    10,                                  # pad_bottom
                    0,                                    # pad_left
                    0,                                     # pad_right
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

    print("All lipsync attempts failed - will fall back to a static (non-lipsynced) video.")
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
        raw_video = create_static_influencer_video(CHARACTER_IMAGE, audio_path)
    if not raw_video:
        sys.exit(1)

    final_video = finalize_video(raw_video)

    video_description = f"{title}\n\n#Shorts #AIInfluencer #Trending #Hinglish"
    upload_to_youtube(final_video, f"{title} #Shorts", video_description)


if __name__ == "__main__":
    main()
