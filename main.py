import os
import re
import time
import uuid
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

gemini_client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Warning: {e}")

# PixVerse API Keys Load
PIXVERSE_KEYS = [
    os.getenv("PIXVERSE_KEY_1"),
    os.getenv("PIXVERSE_KEY_2"),
    os.getenv("PIXVERSE_KEY_3"),
    os.getenv("PIXVERSE_KEY_4")
]
ACTIVE_PIXVERSE_KEYS = [k for k in PIXVERSE_KEYS if k]


def generate_story_script():
    """Generates a 2-Scene Animated Story Script via Gemini"""
    print("Generating 2-Scene Animated Story Script via Gemini...")

    default_data = {
        "scenes": [
            {
                "prompt": "3D animated cute potato character speaking in a colorful market, 9:16 vertical video",
                "script": "ओ यारों, आज मैं नया कारोबार शुरू करने निकला हूँ!"
            },
            {
                "prompt": "3D animated funny eggplant character arguing furiously, 9:16 vertical video",
                "script": "अरे बैंगन भाई, तुम मुझसे इतना जलते क्यों हो?"
            }
        ]
    }

    if not gemini_client:
        return default_data

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
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
                    clean_prompt = video_prompts[i].strip() + ", 3D animated style, 9:16 vertical video"
                    scenes.append({"prompt": clean_prompt, "script": clean_script})
                return {"scenes": scenes}

        except Exception as e:
            print(f"Gemini Story Error ({model_name}): {e}")

    return default_data


def generate_video_with_pixverse(prompt_text, idx):
    """Generates Text-To-Video using PixVerse API Key Rotation"""
    submit_url = "https://app-api.pixverse.ai/openapi/v2/video/text/generate"

    payload = {
        "prompt": prompt_text,
        "aspect_ratio": "9:16",
        "duration": 5,
        "model": "v6",
        "quality": "540p",
        "water_mark": False
    }

    for key in ACTIVE_PIXVERSE_KEYS:
        headers = {
            "API-KEY": key,
            "Ai-Trace-Id": str(uuid.uuid4()),
            "Content-Type": "application/json"
        }

        print(f"Trying PixVerse Video Request for Scene {idx+1} with Key ending in ...{key[-4:] if len(key)>4 else key}")
        try:
            res = requests.post(submit_url, json=payload, headers=headers, timeout=30)
            if res.status_code == 200:
                res_data = res.json()
                if res_data.get("ErrCode") == 0 and "Resp" in res_data:
                    video_id = res_data["Resp"]["video_id"]
                    print(f"PixVerse Task Created Successfully! Task ID: {video_id}")
                    return poll_pixverse_video(video_id, headers, idx)
                else:
                    print(f"PixVerse Response Error: {res_data.get('ErrMsg')}")
            else:
                print(f"Key failed with HTTP status {res.status_code}. Switching key...")
        except Exception as e:
            print(f"PixVerse Exception: {e}")

    print("All PixVerse API Keys failed or exhausted.")
    return None


def poll_pixverse_video(video_id, headers, idx):
    """Polls status until PixVerse video is ready and downloads it"""
    status_url = f"https://app-api.pixverse.ai/openapi/v2/video/result/{video_id}"
    print(f"Waiting for PixVerse to render video clip {idx+1}...")

    for _ in range(30):  # Poll up to 5 minutes
        time.sleep(10)
        try:
            res = requests.get(status_url, headers=headers, timeout=20)
            if res.status_code == 200:
                res_data = res.json()
                resp = res_data.get("Resp", {})
                status = resp.get("status")

                if status == 1 or resp.get("url"):  # 1 = Success
                    download_url = resp.get("url")
                    print(f"Downloading PixVerse rendered video: {download_url}")
                    vid_bytes = requests.get(download_url, timeout=60).content
                    output_file = f"pixverse_raw_{idx}.mp4"
                    with open(output_file, "wb") as f:
                        f.write(vid_bytes)
                    return output_file
                elif status == 2:  # Failed
                    print("PixVerse Server Error: Generation Failed.")
                    return None
        except Exception as e:
            print(f"Polling Exception: {e}")

    return None


def assemble_scene(video_file, script_text, idx):
    """Combines PixVerse Video with TTS Audio via FFmpeg"""
    audio_file = f"audio_{idx}.mp3"
    tts = gTTS(text=script_text, lang="hi", slow=False)
    tts.save(audio_file)

    output_clip = f"clip_{idx}.mp4"
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", video_file,
        "-i", audio_file,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-y",
        output_clip
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    return output_clip


def merge_clips(clip_files, final_output="final_short.mp4"):
    """Merges scene clips into a single short"""
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
    print("=== PixVerse Real AI Video Bot Started ===")

    if not ACTIVE_PIXVERSE_KEYS:
        print("ERROR: No PixVerse API Keys found in Repository Secrets!")
        exit(1)

    story = generate_story_script()
    scenes = story["scenes"]
    final_clips = []

    for idx, scene in enumerate(scenes):
        print(f"\n--- Processing Scene {idx+1} ---")
        raw_video = generate_video_with_pixverse(scene["prompt"], idx)
        if raw_video:
            clip = assemble_scene(raw_video, scene["script"], idx)
            final_clips.append(clip)

    if final_clips:
        final_video = merge_clips(final_clips)
        print(f"\nSUCCESS: Multi-Scene Real Video Generated: {final_video}")
    else:
        print("\nFAILED: Could not generate video scenes.")
