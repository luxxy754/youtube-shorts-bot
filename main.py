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
HF_TOKEN = os.getenv("HF_TOKEN", "")

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

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash"]
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
                    clean_prompt = video_prompts[i].strip() + ", 3D Pixar animated style, 9:16 vertical video"
                    scenes.append({"prompt": clean_prompt, "script": clean_script})
                return {"scenes": scenes}

        except Exception as e:
            print(f"Gemini Story Error ({model_name}): {e}")

    return default_data


def generate_video_huggingface(prompt_text, idx):
    """Generates Video via Hugging Face Free Inference API (Wan2.1 Model)"""
    print(f"Submitting Scene {idx+1} to Hugging Face Free Video Engine...")
    
    API_URL = "https://api-inference.huggingface.co/models/Wan-AI/Wan2.1-T2V-1.4B"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}

    payload = {
        "inputs": prompt_text,
        "parameters": {
            "num_inference_steps": 25,
            "guidance_scale": 6.0
        }
    }

    for attempt in range(5):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            
            if response.status_code == 200:
                out_file = f"hf_scene_{idx}.mp4"
                with open(out_file, "wb") as f:
                    f.write(response.content)
                print(f"Scene {idx+1} video rendered successfully!")
                return out_file
            
            elif response.status_code == 503:
                estimated_time = response.json().get("estimated_time", 20)
                print(f"Model loading on HF servers... Waiting {int(estimated_time)}s.")
                time.sleep(int(estimated_time))
            else:
                print(f"HF Error Status {response.status_code}: {response.text}")
                time.sleep(10)
        except Exception as e:
            print(f"Hugging Face Exception: {e}")
            time.sleep(10)
            
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
    print("=== Fully Automated Free AI Short Video Bot Started ===")

    if not HF_TOKEN:
        print("ERROR: HF_TOKEN Secret missing in GitHub Repository!")
        exit(1)

    story = generate_story_script()
    scenes = story["scenes"]
    final_clips = []

    for idx, scene in enumerate(scenes):
        print(f"\n--- Processing Scene {idx+1} ---")
        raw_video = generate_video_huggingface(scene["prompt"], idx)
        if raw_video:
            clip = assemble_scene(raw_video, scene["script"], idx)
            final_clips.append(clip)

    if final_clips:
        final_video = merge_clips(final_clips)
        print(f"\nSUCCESS: Fully Automated Video Short Ready: {final_video}")
    else:
        print("\nFAILED: Video generation unsuccessful.")
