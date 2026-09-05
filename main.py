import os
import sys
import time
import requests
import subprocess
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

try:
    from gradio_client import Client
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False

# ==================== CONFIGURATION ====================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
HF_TOKENS = [
    os.getenv("HF_TOKEN", ""),
    os.getenv("HF_TOKEN_2", ""),
    os.getenv("HF_TOKEN_3", ""),
]
HF_TOKENS = [t for t in HF_TOKENS if t.strip()]
HF_SPACE = os.getenv("HF_VIDEO_SPACES", "Wan-AI/Wan2.1")
NUM_SCENES = int(os.getenv("NUM_SCENES", "4"))

# YouTube Credentials
YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN", "")

print("YouTube Shorts Visual Bot Initialized.")

def generate_cat_prompts():
    """Generates funny/cool cat 3D animation prompts similar to popular reels."""
    prompts = [
        "A cute fat orange cat wearing a gold chain walking with a little duck, 3D Pixar style, cinematic lighting",
        "A cool fat orange cat wearing sunglasses riding a small motorcycle with a duck, funny, vibrant colors",
        "A happy fat orange cat wearing a chef hat cooking fried chicken in a kitchen pan, humorous 3D animation",
        "A fat orange cat wearing cool sunglasses dancing energetically with funny expressions, vibrant 3D style"
    ]
    return "Cute Cat Adventures #Shorts", prompts

def generate_animated_clip_hf(prompt_text, idx):
    """Generates a real AI video clip using Hugging Face Free Spaces using correct fn_index."""
    if not GRADIO_AVAILABLE:
        print("Gradio client not available.")
        return None

    tokens_to_try = HF_TOKENS if HF_TOKENS else [""]
    
    for token_idx, token in enumerate(tokens_to_try):
        for space_id in HF_SPACE.split(","):
            space_id = space_id.strip()
            try:
                print(f"Trying HF Space '{space_id}' using Token #{token_idx + 1}...")
                if token:
                    os.environ["HF_TOKEN"] = token
                
                client = Client(space_id)
                result = client.predict(prompt=prompt_text, fn_index=0)
                
                if result:
                    video_path = result[0] if isinstance(result, (list, tuple)) else result
                    if video_path and os.path.exists(str(video_path)):
                        output_file = f"scene_{idx}_hf.mp4"
                        os.rename(str(video_path), output_file)
                        print(f"Successfully generated video clip {idx} via HF.")
                        return output_file
            except Exception as e:
                print(f"HF Space {space_id} failed: {e}")
                continue
                
    print(f"Warning: HF failed for scene {idx}. Using fallback zoom-in effect.")
    return None

def create_fallback_video(prompt_text, idx):
    """Creates a basic zoom-in video using FFmpeg if HF fails."""
    output_file = f"scene_{idx}_fallback.mp4"
    img_path = f"scene_{idx}.jpg"
    img_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt_text)}?width=1080&height=1920&nologo=true"
    
    downloaded = False
    for attempt in range(3):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(img_url, headers=headers, timeout=30)
            if response.status_code == 200:
                with open(img_path, "wb") as handler:
                    handler.write(response.content)
                downloaded = True
                break
        except Exception:
            time.sleep(2)
            
    if not downloaded or not os.path.exists(img_path):
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=orange:s=1080:1920", "-vframes", "1", img_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", img_path,
        "-t", "5", "-vf", "scale=2000:3556,zoompan=z='min(zoom+0.0015,1.5)':d=125:s=1080:1920",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", output_file
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_file

def upload_to_youtube(video_path, title):
    """Uploads the generated short video to YouTube using OAuth2 tokens."""
    if not YT_CLIENT_ID or not YT_CLIENT_SECRET or not YT_REFRESH_TOKEN:
        print("YouTube credentials missing in secrets! Skipping upload.")
        return

    print("Authenticating with YouTube API...")
    creds = Credentials(
        None,
        refresh_token=YT_REFRESH_TOKEN,
        client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token"
    )
    
    youtube = build("youtube", "v3", credentials=creds)
    
    body = {
        "snippet": {
            "title": f"{title} 🐱 #Shorts",
            "description": "Funny and cute cat adventures! Don't forget to subscribe for daily shorts. #cats #shorts #animation",
            "tags": ["shorts", "funny cats", "animation", "cute cat"],
            "categoryId": "24"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }
    
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    
    print("Uploading video to YouTube...")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")
            
    print(f"Successfully uploaded! Video ID: {response.get('id')}")

def main():
    title, scene_prompts = generate_cat_prompts()
    
    video_clips = []
    for idx, prompt in enumerate(scene_prompts[:NUM_SCENES]):
        clip = generate_animated_clip_hf(prompt, idx)
        if not clip:
            clip = create_fallback_video(prompt, idx)
        video_clips.append(clip)
        
    with open("clips.txt", "w") as f:
        for clip in video_clips:
            f.write(f"file '{clip}'\n")
            
    final_video = "final_output.mp4"
    print("Merging video clips into final short...")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "clips.txt", "-c", "copy", final_video], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    if os.path.exists(final_video):
        print(f"Short video generated successfully: {final_video}")
        upload_to_youtube(final_video, title)
    else:
        print("Error: Final video generation failed.")

if __name__ == "__main__":
    main()
