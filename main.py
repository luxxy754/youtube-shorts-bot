import os
import sys
import json
import time
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
NUM_SCENES = int(os.getenv("NUM_SCENES", "1")) # Influencer ke liye single scene ya continuous clip behtar hai

POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", "")
POLLINATIONS_VIDEO_MODEL = os.getenv("POLLINATIONS_VIDEO_MODEL", "wan-fast")
POLLINATIONS_VIDEO_DURATION = os.getenv("POLLINATIONS_VIDEO_DURATION", "10")

YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN", "")
YT_PRIVACY_STATUS = os.getenv("YT_PRIVACY_STATUS", "public")

print("AI Influencer YouTube Shorts Bot Initialized.")

def generate_influencer_content():
    """Gemini se aajkal ke trending topics par Hinglish script aur visual prompt generate karwata hai."""
    fallback_title = "Aaj Ki Viral Baat!"
    fallback_script = "Dosto, kya aapko pata hai aajkal AI ki duniya mein kya chal raha hai? Har koi bas apni digital life ko upgrade karne mein laga hai!"
    fallback_prompt = "A beautiful slim Russian-style AI influencer woman sitting on a cozy modern sofa in a stylish room, holding a studio microphone, talking to the camera with expressive friendly face, 3D Pixar cinematic lighting, 9:16 aspect ratio"

    if not GEMINI_API_KEY:
        print("No GEMINI_API_KEY set - using fallback script and prompt.")
        return fallback_title, fallback_script, fallback_prompt

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    instruction = (
        "Generate a trending short script for an AI influencer YouTube Short in Hinglish (Hindi/Urdu mixed naturally with cool English words). "
        "Also generate a visual prompt for her appearance: a slim Russian-style beautiful lady sitting on a sofa with a studio microphone. "
        "Reply ONLY with valid JSON, no markdown, no code fences, in this exact shape: "
        '{"title": "catchy title", "script": "Hinglish voiceover script under 40 words", "prompt": "visual prompt for the video generator"}'
    )
    body = {"contents": [{"parts": [{"text": instruction}]}]}

    try:
        print("Asking Gemini for trending influencer script and visuals...")
        resp = requests.post(api_url, json=body, timeout=30)
        if resp.status_code != 200:
            return fallback_title, fallback_script, fallback_prompt

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
            str(parsed.get("prompt") or fallback_prompt).strip()
        )
    except Exception as e:
        print(f"Gemini error: {e}. Using fallbacks.")
        return fallback_title, fallback_script, fallback_prompt

def generate_voiceover(script_text):
    """Free gTTS ya ElevenLabs se Hinglish voiceover banata hai."""
    audio_path = "voiceover.mp3"
    try:
        from gtts import gTTS
        print("Generating voiceover using gTTS (Hindi/Urdu)...")
        tts = gTTS(text=script_text, lang='hi', slow=False)
        tts.save(audio_path)
        return audio_path
    except Exception as e:
        print(f"Voiceover generation failed: {e}")
        return None

def create_influencer_video(prompt_text, audio_path):
    """Pollinations ya FFmpeg fallback se video banakar audio ke sath merge karta hai."""
    video_file = "scene_video.mp4"
    img_path = "influencer.jpg"
    
    img_url = f"[https://image.pollinations.ai/prompt/](https://image.pollinations.ai/prompt/){requests.utils.quote(prompt_text)}?width=1080&height=1920&nologo=true"
    
    try:
        print("Downloading influencer base image...")
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(img_url, headers=headers, timeout=30)
        if resp.status_code == 200:
            with open(img_path, "wb") as f:
                f.write(resp.content)
    except Exception as e:
        print(f"Image download failed: {e}")

    if not os.path.exists(img_path):
        # Emergency solid color frame agar download fail ho jaye
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=purple:s=1080:1920", "-vframes", "1", img_path])

    # FFmpeg zoompan effect to make it dynamic
    camera_move = "zoompan=z='min(zoom+0.0015,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=150:s=1080x1920"
    
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", img_path,
        "-i", audio_path,
        "-vf", f"scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,{camera_move}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", video_file
    ]
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0 or not os.path.exists(video_file):
        print("Error creating final video.")
        return None

    return video_file

def upload_to_youtube(video_path, title, description, tags=None):
    """Aapka purana YouTube auto-upload function (issay change nahi kiya gaya)."""
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
                "tags": tags or ["AI", "Shorts", "Influencer"],
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
    title, script, prompt = generate_influencer_content()
    print(f"Title: {title}")
    print(f"Script: {script}")

    audio_path = generate_voiceover(script)
    if not audio_path:
        sys.exit(1)

    final_video = create_influencer_video(prompt, audio_path)
    if not final_video:
        sys.exit(1)

    video_description = f"{title}\n\n#Shorts #AIInfluencer #Trending #Hinglish"
    upload_to_youtube(final_video, f"{title} #Shorts", video_description)

if __name__ == "__main__":
    main()
