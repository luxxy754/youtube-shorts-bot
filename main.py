import os
import time
import random
import requests
import subprocess
from gtts import gTTS

# Gemini SDK Setup
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ==========================================
# 1. API KEYS SETUP (KEY ROTATION)
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Load and parse multiple comma-separated Kling keys
raw_kling_keys = os.getenv("KLING_API_KEY", "")
KLING_KEYS_LIST = [k.strip() for k in raw_kling_keys.split(",") if k.strip()]

gemini_client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Warning: {e}")


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def generate_script():
    """Gemini AI Script Generation"""
    print("Generating Hindi Script via Gemini...")
    if not gemini_client:
        return "ओ यारों, मेरा यार ना रहा मेरा!"

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    prompt_text = "Write 1 super short emotional/funny Hindi line for animated veggies crying. Under 8 words."

    for model_name in models_to_try:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt_text
            )
            script_text = response.text.strip()
            print(f"Generated Script: {script_text}")
            return script_text
        except Exception as e:
            print(f"Gemini Error ({model_name}): {e}")

    return "ओ यारों, मेरा यार ना रहा मेरा!"


def generate_audio(text, output_file="hindi_audio.mp3"):
    """gTTS Audio Generation"""
    print("Generating Audio via gTTS...")
    tts = gTTS(text=text, lang="hi", slow=False)
    tts.save(output_file)
    print(f"Audio saved: {output_file}")
    return output_file


def generate_video_kling(prompt_text, output_video="ai_kling_video.mp4"):
    """Kling AI Generation with Smart Key Rotation Loop"""
    if not KLING_KEYS_LIST:
        print("CRITICAL ERROR: No Kling API Keys found in GitHub Secrets!")
        return None

    # Shuffle keys to balance usage across all accounts
    available_keys = KLING_KEYS_LIST.copy()
    random.shuffle(available_keys)

    url = "https://api.klingai.com/v1/videos/text2video"

    for index, current_key in enumerate(available_keys, 1):
        print(f"Attempting Video Generation with Kling Key #{index} (Prefix: {current_key[:15]}...)...")

        headers = {
            "Authorization": f"Bearer {current_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model_name": "kling-v1",
            "prompt": prompt_text,
            "aspect_ratio": "9:16",
            "duration": "5"
        }

        try:
            res = requests.post(url, json=payload, headers=headers)
            data = res.json()

            if data.get("code") != 0:
                print(f"Key #{index} failed with response: {data}. Switching to next key...")
                continue

            task_id = data["data"]["task_id"]
            print(f"Task successfully created! Task ID: {task_id}")

            # Polling for task completion
            task_url = f"https://api.klingai.com/v1/videos/text2video/{task_id}"
            while True:
                time.sleep(10)
                poll_res = requests.get(task_url, headers=headers).json()
                status = poll_res.get("data", {}).get("task_status")
                print(f"Kling Task Status: {status}")

                if status == "succeed":
                    video_url = poll_res["data"]["task_result"]["videos"][0]["url"]
                    print(f"Downloading Video from: {video_url}")
                    v_res = requests.get(video_url)
                    if v_res.status_code == 200:
                        with open(output_video, "wb") as f:
                            f.write(v_res.content)
                        print(f"Saved base video to: {output_video}")
                        return output_video
                    break
                elif status in ["failed", "canceled"]:
                    print(f"Task failed on server side. Retrying next key...")
                    break

        except Exception as e:
            print(f"Exception with Key #{index}: {e}. Trying next key...")
            continue

    print("All provided Kling API Keys failed or exhausted daily quotas.")
    return None


def merge_video_audio(video_file, audio_file, final_output="final_short.mp4"):
    """FFmpeg Syncing"""
    print("Syncing Video & Voiceover via FFmpeg...")
    command = [
        "ffmpeg",
        "-stream_loop", "-1",
        "-i", video_file,
        "-i", audio_file,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-y",
        final_output
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        print(f"SUCCESS: Final Short Video produced at '{final_output}'")
        return final_output
    else:
        print(f"FFmpeg Sync Error: {result.stderr.decode('utf-8')}")
        return None


# ==========================================
# 3. MAIN EXECUTION PIPELINE
# ==========================================
if __name__ == "__main__":
    print("=== YouTube Shorts AI Automation Started ===")

    script_text = generate_script()
    audio_path = generate_audio(script_text)

    prompt = (
        "3D Pixar style cinematic video of cute animated vegetables (onion, carrot, potato, pumpkin) "
        "crying and walking together in a rural Indian village street, detailed character expressions, "
        "dramatic emotional lighting, 4k resolution, vertical 9:16 short video."
    )

    generated_video = generate_video_kling(prompt)

    if generated_video and audio_path:
        merge_video_audio(generated_video, audio_path)
        print("\n=== Pipeline Executed Successfully! ===")
    else:
        print("\n=== Pipeline Failed: Could not generate AI video ===")
