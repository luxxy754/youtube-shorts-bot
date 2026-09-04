import os
import re
import sys
import time
import uuid
import inspect
import requests
import subprocess
from gtts import gTTS

# Gemini Setup
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN", "")
YT_PRIVACY_STATUS = os.getenv("YT_PRIVACY_STATUS", "private")

NUM_SCENES = int(os.getenv("NUM_SCENES", "5"))

ELEVEN_KEYS = [
    os.getenv("ELEVEN_KEY_1", ""),
    os.getenv("ELEVEN_KEY_2", ""),
    os.getenv("ELEVEN_KEY_3", ""),
]
ELEVEN_KEYS = [k for k in ELEVEN_KEYS if k.strip()]

gemini_client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Warning: {e}")


def generate_story_script():
    """Generates a strict script featuring ONLY cute cats and little baby chicks in 3D Pixar style."""
    print("Generating Cat & Chick Story Script via Gemini...")

    if not gemini_client:
        return {"scenes": [
            {"prompt": "Adorable fluffy 3D Pixar cartoon cat with big expressive eyes talking happily, vibrant colors, vertical 9:16", "script": "O yaaron, aaj maine ek bohot hi mazedaar machli dekhi!"},
            {"prompt": "Super cute tiny fluffy yellow baby chick chirping cheerfully, 3D Disney Pixar style, vibrant lighting, vertical 9:16", "script": "Arre kahan hai machli, mujhe bhi dikhao na!"}
        ]}

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest"]

    format_lines = []
    for i in range(1, NUM_SCENES + 1):
        format_lines.append(f"SCENE {i} PROMPT: [Video prompt]")
        format_lines.append(f"SCENE {i} SCRIPT: [Hindi dialogue line]")
    format_block = "\n".join(format_lines)

    prompt_text = (
        f"Create a funny, super cute {NUM_SCENES}-scene animated Hindi short story starring ONLY cute cats and little fluffy yellow chicks. "
        "ABSOLUTELY NO pandas, NO bears, NO strange animals, ONLY cats and chicks. "
        "Each scene must feature a cute cat or a baby chick doing funny expressive talks in a stunning 3D Disney/Pixar style (max 12 words) "
        "and 1 pure Hindi dialogue line (roughly 6-8 seconds).\n\n"
        "STRICT FORMAT (no extra text before/after):\n" + format_block
    )

    for model_name in models_to_try:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt_text
            )
            raw_text = (response.text or "").strip()

            scenes = []
            video_prompts = re.findall(r'SCENE \d+ PROMPT:\s*(.*)', raw_text)
            scripts = re.findall(r'SCENE \d+ SCRIPT:\s*(.*)', raw_text)

            if len(video_prompts) >= NUM_SCENES and len(scripts) >= NUM_SCENES:
                for i in range(NUM_SCENES):
                    clean_script = re.sub(r'\(.*?\)', '', scripts[i]).replace('*', '').replace('"', '').strip()
                    clean_prompt = video_prompts[i].strip() + ", cute fluffy cat or tiny baby chick, 3D Pixar style animation, vibrant cinematic lighting, highly detailed, vertical 9:16"
                    if clean_script and clean_prompt:
                        scenes.append({"prompt": clean_prompt, "script": clean_script})
                if len(scenes) == NUM_SCENES:
                    return {"scenes": scenes}
        except Exception as e:
            print(f"Gemini Story Error ({model_name}): {e}")

    return {"scenes": [
        {"prompt": "Adorable fluffy 3D Pixar cartoon cat with big expressive eyes talking happily, vibrant colors, vertical 9:16", "script": "O yaaron, aaj maine ek bohot hi mazedaar machli dekhi!"},
        {"prompt": "Super cute tiny fluffy yellow baby chick chirping cheerfully, 3D Disney Pixar style, vibrant lighting, vertical 9:16", "script": "Arre kahan hai machli, mujhe bhi dikhao na!"}
    ]}


def generate_animated_clip_pollinations(prompt_text, audio_duration, idx):
    """Generates a cat/chick image and applies mouth-area volume deformation lipsync + head tilt via FFmpeg."""
    enhanced_prompt = f"{prompt_text}, ultra-detailed cute character, vibrant colors, 8k resolution, cinematic lighting"
    img_prompt = requests.utils.quote(enhanced_prompt)
    img_url = f"https://image.pollinations.ai/prompt/{img_prompt}?width=1080&height=1920&nologo=true"
    img_file = f"scene_{idx}_pollinations.jpg"

    try:
        res = requests.get(img_url, timeout=60)
        res.raise_for_status()
        with open(img_file, "wb") as f:
            f.write(res.content)
    except Exception as e:
        print(f"Pollinations image fetch failed: {e}")
        return None

    out_file = f"scene_{idx}_animated.mp4"
    fps = 25
    frames = int(audio_duration * fps)
    
    mouth_geq = (
        "geq="
        "r='r(X,Y+if(between(X,378,702)*between(Y,1056,1382), sin(T*22)*8, 0))':"
        "g='g(X,Y+if(between(X,378,702)*between(Y,1056,1382), sin(T*22)*8, 0))':"
        "b='b(X,Y+if(between(X,378,702)*between(Y,1056,1382), sin(T*22)*8, 0))'"
    )

    zoom_cmd = [
        "ffmpeg",
        "-loop", "1",
        "-i", img_file,
        "-vf",
        (
            f"scale=1080:1920,"
            f"rotate='0.02*sin(2*PI*t/2.2)':ow=1080:oh=1920:c=none,"
            f"{mouth_geq},"
            f"zoompan=z='min(zoom+0.0008,1.15)':d={frames}:s=1080x1920:fps={fps}"
        ),
        "-t", f"{audio_duration:.2f}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-y",
        out_file
    ]
    
    try:
        subprocess.run(zoom_cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg lipsync motion failed: {e.stderr}")
        fallback_cmd = [
            "ffmpeg", "-loop", "1", "-i", img_file,
            "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.001,1.2)':d={frames}:s=1080x1920:fps={fps}",
            "-t", f"{audio_duration:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", out_file
        ]
        subprocess.run(fallback_cmd, check=True, capture_output=True, text=True)

    return out_file


def get_media_duration(path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def process_scene(scene, idx):
    print(f"\n--- Processing Scene {idx + 1} ---")
    audio_file = f"audio_{idx}.mp3"
    script_text = scene["script"]

    eleven_success = False
    for key in ELEVEN_KEYS:
        try:
            url = "https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB"
            headers = {"xi-api-key": key, "Content-Type": "application/json"}
            payload = {
                "text": script_text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {"stability": 0.4, "similarity_boost": 0.8}
            }
            res = requests.post(url, json=payload, headers=headers, timeout=20)
            if res.status_code == 200 and res.content:
                with open(audio_file, "wb") as f:
                    f.write(res.content)
                eleven_success = True
                break
        except Exception:
            pass

    if not eleven_success:
        try:
            tts = gTTS(text=script_text, lang="hi", slow=False)
            tts.save(audio_file)
        except Exception as e:
            print(f"gTTS fallback failed: {e}")
            return None

    audio_duration = get_media_duration(audio_file)

    video_file = generate_animated_clip_pollinations(scene["prompt"], audio_duration, idx)
    if not video_file:
        return None

    output_clip = f"clip_{idx}.mp4"
    sync_cmd = [
        "ffmpeg", "-i", video_file, "-i", audio_file,
        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
        "-shortest", "-y", output_clip
    ]
    subprocess.run(sync_cmd, check=True, capture_output=True, text=True)
    return output_clip


def merge_clips(clip_files, final_output="final_short.mp4"):
    with open("files.txt", "w") as f:
        for clip in clip_files:
            f.write(f"file '{clip}'\n")

    concat_cmd = [
        "ffmpeg", "-f", "concat", "-safe", "0",
        "-i", "files.txt", "-c", "copy", "-y", final_output
    ]
    subprocess.run(concat_cmd, check=True, capture_output=True, text=True)
    return final_output


def upload_to_youtube(video_path, title="Cute Cat & Chick Short #Shorts", description="A funny 3D Pixar style animated short featuring cute cats and chicks! #shorts #cats #animation"):
    print("Authenticating and uploading to YouTube...")
    if not YT_CLIENT_ID or not YT_CLIENT_SECRET or not YT_REFRESH_TOKEN:
        print("YouTube upload skipped: Missing credentials.")
        return False

    # Step 1: Get Access Token from Refresh Token
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "client_id": YT_CLIENT_ID,
        "client_secret": YT_CLIENT_SECRET,
        "refresh_token": YT_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    
    try:
        res = requests.post(token_url, data=token_data)
        res.raise_for_status()
        access_token = res.json().get("access_token")
    except Exception as e:
        print(f"Failed to refresh YouTube access token: {e}")
        return False

    # Step 2: Initialize Resumable Upload
    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["shorts", "cat", "chick", "pixar", "animation", "funny"],
            "categoryId": "1"
        },
        "status": {
            "privacyStatus": YT_PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False
        }
    }

    init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4"
    }

    try:
        init_res = requests.post(init_url, headers=headers, json=metadata)
        init_res.raise_for_status()
        upload_url = init_res.headers.get("Location")
    except Exception as e:
        print(f"Failed to initialize YouTube upload: {e}")
        return False

    # Step 3: Upload Video File
    try:
        with open(video_path, "rb") as f:
            video_data = f.read()
        
        upload_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "video/mp4",
            "Content-Length": str(len(video_data))
        }
        upload_res = requests.put(upload_url, headers=upload_headers, data=video_data)
        upload_res.raise_for_status()
        print("SUCCESS: Video uploaded to YouTube successfully!")
        return True
    except Exception as e:
        print(f"Failed to upload video binary to YouTube: {e}")
        return False


if __name__ == "__main__":
    print("=== Strict Cat & Chick Short Bot Started ===")
    story = generate_story_script()
    scenes = story["scenes"]
    final_clips = []

    for idx, scene in enumerate(scenes):
        try:
            clip = process_scene(scene, idx)
            if clip:
                final_clips.append(clip)
        except Exception as e:
            print(f"Scene {idx + 1} failed: {e}")

    if final_clips:
        try:
            final_video = merge_clips(final_clips)
            total_duration = get_media_duration(final_video)
            
            # YouTube Upload Trigger
            upload_to_youtube(final_video)
            
        except Exception as e:
            print(f"\nFAILED: {e}")
            sys.exit(1)
        print(f"\nSUCCESS: Short Ready: {final_video} (~{total_duration:.1f}s)")
    else:
        print("\nFAILED: No clips produced.")
        sys.exit(1)
