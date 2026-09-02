import os
import re
import time
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
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")

gemini_client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Warning: {e}")


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

    # Updated active Gemini models
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
                    clean_prompt = video_prompts[i].strip() + ", 3D animated Pixar style, 9:16 vertical video"
                    scenes.append({"prompt": clean_prompt, "script": clean_script})
                return {"scenes": scenes}

        except Exception as e:
            print(f"Gemini Story Error ({model_name}): {e}")

    return default_data


def generate_video_replicate(prompt_text, idx):
    """Generates Video via Replicate Wan 2.1 Model with Rate Limit handling"""
    print(f"Submitting Scene {idx+1} to Replicate Video Engine...")
    
    # Free tier rate limits (1 req / 10 sec) se bachne ke liye cooldown delay
    time.sleep(12)

    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    # Model deployment endpoint for Wan 2.1
    url = "https://api.replicate.com/v1/models/wan-video/wan-2.1-t2v-480p/predictions"
    payload = {
        "input": {
            "prompt": prompt_text,
            "aspect_ratio": "9:16"
        }
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)

        # Retrying after rate-limit cooldown if 429 happens
        if res.status_code == 429:
            print("Rate limit reached! Waiting 15 seconds before retrying...")
            time.sleep(15)
            res = requests.post(url, json=payload, headers=headers, timeout=30)

        if res.status_code in [200, 201]:
            pred_data = res.json()
            pred_id = pred_data.get("id")
            poll_url = pred_data.get("urls", {}).get("get") or f"https://api.replicate.com/v1/predictions/{pred_id}"
            
            print("Waiting for Wan 2.1 to render video...")
            for _ in range(40):
                time.sleep(10)
                status_res = requests.get(poll_url, headers=headers).json()
                status = status_res.get("status")
                
                if status == "succeeded":
                    output_url = status_res.get("output")
                    if isinstance(output_url, list):
                        output_url = output_url[0]
                    
                    vid_bytes = requests.get(output_url, timeout=60).content
                    out_file = f"replicate_scene_{idx}.mp4"
                    with open(out_file, "wb") as f:
                        f.write(vid_bytes)
                    print(f"Scene {idx+1} video rendered successfully!")
                    return out_file
                elif status == "failed":
                    print(f"Replicate rendering failed: {status_res.get('error')}")
                    return None
        else:
            print(f"Replicate API Error: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Replicate Exception: {e}")
    return None


def assemble_scene(video_file, script_text, idx):
    """Syncs Audio with AI Video"""
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
    print("=== Fully Automated Replicate Video Bot Started ===")

    if not REPLICATE_API_TOKEN:
        print("ERROR: REPLICATE_API_TOKEN Secret missing!")
        exit(1)

    story = generate_story_script()
    scenes = story["scenes"]
    final_clips = []

    for idx, scene in enumerate(scenes):
        print(f"\n--- Processing Scene {idx+1} ---")
        raw_video = generate_video_replicate(scene["prompt"], idx)
        if raw_video:
            clip = assemble_scene(raw_video, scene["script"], idx)
            final_clips.append(clip)

    if final_clips:
        final_video = merge_clips(final_clips)
        print(f"\nSUCCESS: Fully Automated Video Short Ready: {final_video}")
    else:
        print("\nFAILED: Video generation unsuccessful.")
