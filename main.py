import os
import re
import time
import jwt
import requests
import subprocess
from gtts import gTTS

# Gemini SDK Setup
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
KLING_ACCESS_KEY = os.getenv("KLING_ACCESS_KEY", "")
KLING_SECRET_KEY = os.getenv("KLING_SECRET_KEY", "")

gemini_client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Warning: {e}")


def get_kling_token():
    """Generates JWT Bearer Token for Kling AI API Authentication"""
    headers = {
        "alg": "HS256",
        "typ": "JWT"
    }
    payload = {
        "iss": KLING_ACCESS_KEY,
        "exp": int(time.time()) + 1800, # Valid for 30 minutes
        "nbf": int(time.time()) - 5
    }
    token = jwt.encode(payload, KLING_SECRET_KEY, algorithm="HS256", headers=headers)
    return token


def generate_story_script():
    """Generates 2-Scene Story Script via Gemini"""
    print("Generating Story Script via Gemini...")

    default_data = {
        "scenes": [
            {
                "prompt": "3D Pixar style animated cute potato character talking dynamically in colorful market",
                "script": "ओ यारों, आज मैं नया कारोबार शुरू करने निकला हूँ!"
            },
            {
                "prompt": "3D Pixar style animated angry eggplant character shouting furiously",
                "script": "अरे बैंगन भाई, तुम मुझसे इतना जलते क्यों हो?"
            }
        ]
    }

    if not gemini_client:
        return default_data

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest"]
    prompt_text = (
        "Create a funny 2-scene animated Hindi short story starring 3D cartoon veggies. "
        "Each scene must have a visual video prompt in English describing action/motion (max 12 words) and 1 pure Hindi dialogue line.\n\n"
        "STRICT FORMAT:\n"
        "SCENE 1 PROMPT: [Video prompt]\n"
        "SCENE 1 SCRIPT: [Hindi dialogue line]\n"
        "SCENE 2 PROMPT: [Video prompt]\n"
        "SCENE 2 SCRIPT: [Hindi dialogue line]"
    )

    for model_name in models_to_try:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt_text
            )
            raw_text = response.text.strip()
            
            scenes = []
            video_prompts = re.findall(r'SCENE \d+ PROMPT:\s*(.*)', raw_text)
            scripts = re.findall(r'SCENE \d+ SCRIPT:\s*(.*)', raw_text)

            if len(video_prompts) >= 2 and len(scripts) >= 2:
                for i in range(2):
                    clean_script = re.sub(r'\(.*?\)', '', scripts[i]).replace('*', '').replace('"', '').strip()
                    clean_prompt = video_prompts[i].strip() + ", 3D animated Pixar style, vertical portrait"
                    scenes.append({"prompt": clean_prompt, "script": clean_script})
                return {"scenes": scenes}

        except Exception as e:
            print(f"Gemini Story Error ({model_name}): {e}")

    return default_data


def generate_video_kling(prompt_text, idx):
    """Generates Video via Kling AI Direct API"""
    print(f"Submitting Scene {idx+1} to Kling AI Video Engine...")

    token = get_kling_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    url = "https://api.klingai.com/v1/videos/text2video"
    payload = {
        "model_name": "kling-v1",
        "prompt": prompt_text,
        "aspect_ratio": "9:16",
        "duration": "5"
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if res.status_code == 200:
            data = res.json()
            if data.get("code") == 0:
                task_id = data["data"]["task_id"]
                print(f"Kling Task ID Created: {task_id}. Polling for completion...")

                # Status check loop
                poll_url = f"https://api.klingai.com/v1/videos/text2video/{task_id}"
                for _ in range(40):
                    time.sleep(10)
                    # Refresh token if needed
                    current_token = get_kling_token()
                    poll_headers = {"Authorization": f"Bearer {current_token}"}
                    
                    status_res = requests.get(poll_url, headers=poll_headers).json()
                    
                    if status_res.get("code") == 0:
                        task_status = status_res["data"]["task_status"]
                        
                        if task_status == "succeeded":
                            video_url = status_res["data"]["task_result"]["videos"][0]["url"]
                            vid_bytes = requests.get(video_url, timeout=60).content
                            out_file = f"kling_scene_{idx}.mp4"
                            with open(out_file, "wb") as f:
                                f.write(vid_bytes)
                            print(f"Scene {idx+1} video rendered successfully by Kling AI!")
                            return out_file
                        elif task_status == "failed":
                            print(f"Kling Rendering Failed: {status_res['data'].get('task_status_msg')}")
                            return None
                    else:
                        print(f"Kling Polling Error: {status_res.get('message')}")
            else:
                print(f"Kling API Error Code: {data.get('code')} - {data.get('message')}")
        else:
            print(f"Kling API HTTP Error: {res.status_code} - {res.text}")

    except Exception as e:
        print(f"Kling AI Exception: {e}")

    return None


def assemble_scene(video_file, script_text, idx):
    """Syncs Audio with Kling AI Video"""
    audio_file = f"audio_{idx}.mp3"
    tts = gTTS(text=script_text, lang="hi", slow=False)
    tts.save(audio_file)

    output_clip = f"clip_{idx}.mp4"
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", video_file,
        "-i", audio_file,
        "-filter_complex", "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v]",
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        "-y",
        output_clip
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    return output_clip


def merge_clips(clip_files, final_output="final_short.mp4"):
    """Merges all video clips into one Short"""
    with open("files.txt", "w") as f:
        for clip in clip_files:
            f.write(f"file '{clip}'\n")

    concat_cmd = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", "files.txt",
        "-c", "copy",
        "-y",
        final_output
    ]
    subprocess.run(concat_cmd, check=True)
    return final_output


if __name__ == "__main__":
    print("=== Fully Automated Kling AI Video Bot Started ===")

    if not KLING_ACCESS_KEY or not KLING_SECRET_KEY:
        print("ERROR: KLING_ACCESS_KEY or KLING_SECRET_KEY Missing in Secrets!")
        exit(1)

    story = generate_story_script()
    scenes = story["scenes"]
    final_clips = []

    for idx, scene in enumerate(scenes):
        print(f"\n--- Processing Scene {idx+1} ---")
        raw_video = generate_video_kling(scene["prompt"], idx)
        if raw_video:
            clip = assemble_scene(raw_video, scene["script"], idx)
            final_clips.append(clip)

    if final_clips:
        final_video = merge_clips(final_clips)
        print(f"\nSUCCESS: Fully Automated Kling Video Short Ready: {final_video}")
    else:
        print("\nFAILED: Video generation unsuccessful.")
