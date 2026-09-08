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

# ==================== CONFIGURATION ====================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ElevenLabs Keys rotation logic (Aapke secrets se keys uthayega)
ELEVEN_KEYS = [
    os.getenv("ELEVEN_KEY_1", ""),
    os.getenv("ELEVEN_KEY_2", ""),
    os.getenv("ELEVEN_KEY_3", "")
]
# Ek popular expressive female voice ID (Rachel ya Bella)
ELEVEN_VOICE_ID = "21m00Tcm4TlvDq8ikWAM" 

YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN", "")
YT_PRIVACY_STATUS = os.getenv("YT_PRIVACY_STATUS", "public")

CHARACTER_IMAGE = "character.jpg"

print("ElevenLabs AI Influencer Bot Initialized.")

def generate_influencer_script():
    """Gemini se aajkal ke trending topics par Hinglish script generate karwata hai."""
    fallback_title = "Aaj Ki Viral Baat!"
    fallback_script = "Dosto, kya aapko pata hai aajkal technology ki duniya mein kya naya chal raha hai? Har koi bas apni digital life ko smart banane mein laga hai!"

    if not GEMINI_API_KEY:
        print("No GEMINI_API_KEY set - using fallback script.")
        return fallback_title, fallback_script

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    instruction = (
        "Generate a trending short script for an AI influencer YouTube Short in Hinglish (Hindi/Urdu mixed naturally with cool English words). "
        "Keep it under 35 words (short and crisp for free tier voice generation), engaging and conversational. "
        "Reply ONLY with valid JSON, no markdown, no code fences, in this exact shape: "
        '{"title": "catchy title", "script": "Hinglish voiceover script"}'
    )
    body = {"contents": [{"parts": [{"text": instruction}]}]}

    try:
        print("Asking Gemini for trending influencer script...")
        resp = requests.post(api_url, json=body, timeout=30)
        if resp.status_code != 200:
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
            str(parsed.get("script") or fallback_script).strip()
        )
    except Exception as e:
        print(f"Gemini error: {e}. Using fallbacks.")
        return fallback_title, fallback_script

def generate_voiceover(script_text):
    """ElevenLabs Free Tier API use karke ultra-realistic female voice banata hai, with gTTS fallback."""
    audio_path = "voiceover.mp3"
    
    # Available keys filter karein
    active_keys = [k for k in ELEVEN_KEYS if k.strip()]
    
    success = False
    if active_keys:
        url = f"[https://api.elevenlabs.io/v1/text-to-speech/](https://api.elevenlabs.io/v1/text-to-speech/){ELEVEN_VOICE_ID}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json"
        }
        payload = {
            "text": script_text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        # Keys rotate karke try karein agar koi limit cross ho gayi ho
        for idx, key in enumerate(active_keys):
            headers["xi-api-key"] = key
            try:
                print(f"Trying ElevenLabs API with key index {idx + 1}...")
                response = requests.post(url, json=payload, headers=headers, timeout=30)
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

    # Agar ElevenLabs fail ho jaye ya keys na hon, toh gTTS use karenge (Free fallback)
    if not success:
        print("Falling back to gTTS for voiceover generation...")
        try:
            from gtts import gTTS
            tts = gTTS(text=script_text, lang='hi', slow=False)
            tts.save(audio_path)
            success = True
        except Exception as e:
            print(f"gTTS fallback also failed: {e}")
            return None

    return audio_path if success else None

def create_static_influencer_video(audio_path):
    """Fixed character image par bina movement ke audio merge karke video banata hai."""
    video_file = "scene_video.mp4"
    
    if not os.path.exists(CHARACTER_IMAGE):
        print(f"Error: {CHARACTER_IMAGE} not found in repository!")
        return None

    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", CHARACTER_IMAGE,
        "-i", audio_path,
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", video_file
    ]
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0 or not os.path.exists(video_file):
        print(f"FFmpeg error: {result.stderr.decode('utf-8')}")
        return None

    return video_file

def upload_to_youtube(video_path, title, description, tags=None):
    """YouTube auto-upload function."""
    if not YOUTUBE_AVAILABLE or not (YT_CLIENT_ID and YT_CLIENT_SECRET and YT_REFRESH_TOKEN):
        print("YouTube credentials missing - skipping upload.")
        return None

    try:
        creds = Credentials(
            token=None, refresh_token=YT_REFRESH_TOKEN,
            client_id=YT_CLIENT_ID, client_secret=YT_CLIENT_SECRET,
            token_uri="[https://oauth2.googleapis.com/token](https://oauth2.googleapis.com/token)",
            scopes=["[https://www.googleapis.com/auth/youtube.upload](https://www.googleapis.com/auth/youtube.upload)"],
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
        print(f"YouTube upload failed: {e}")
        return None

def main():
    title, script = generate_influencer_script()
    print(f"Title: {title}")
    print(f"Script: {script}")

    audio_path = generate_voiceover(script)
    if not audio_path:
        sys.exit(1)

    final_video = create_static_influencer_video(audio_path)
    if not final_video:
        sys.exit(1)

    video_description = f"{title}\n\n#Shorts #AIInfluencer #Trending #Hinglish"
    upload_to_youtube(final_video, f"{title} #Shorts", video_description)

if __name__ == "__main__":
    main()
