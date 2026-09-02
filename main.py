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

# Luma AI SDK Setup
try:
    from lumaai import LumaAI
    LUMA_AVAILABLE = True
except ImportError:
    LUMA_AVAILABLE = False

# ==========================================
# 1. API KEYS SETUP
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LUMA_API_KEY = os.getenv("LUMA_API_KEY", "")
KLING_API_KEY = os.getenv("KLING_API_KEY", "")

gemini_client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Error: {e}")

luma_client = None
if LUMA_AVAILABLE and LUMA_API_KEY:
    try:
        luma_client = LumaAI(api_key=LUMA_API_KEY)
    except Exception as e:
        print(f"Luma Client Init Error: {e}")


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def generate_script():
    """Gemini se Script Generate Karna"""
    print("Generating Script via Gemini...")
    if not gemini_client:
        return "ओ यारों, मेरा यार ना रहा मेरा!"

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    prompt_text = "Write 1 short line in Hindi for a emotional/funny short video of vegetables crying. Under 8 words."

    for model_name in models_to_try:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt_text
            )
            return response.text.strip()
        except Exception as e:
            print(f"Gemini Error ({model_name}): {e}")

    return "ओ यारों, मेरा यार ना रहा मेरा!"


def generate_audio(text, output_file="hindi_audio.mp3"):
    """gTTS Voice Generation"""
    print("Generating Audio via gTTS...")
    tts = gTTS(text=text, lang="hi", slow=False)
    tts.save(output_file)
    return output_file


def generate_video_luma(prompt_text, output_video="ai_luma_video.mp4"):
    """Luma AI Dream Machine (Ray-2) Direct Integration"""
    if not luma_client:
        print("Luma API Key Missing or SDK not initialized.")
        return None

    print("Submitting Luma AI Video Generation Task...")
    try:
        generation = luma_client.generations.create(
            model="ray-2",
            prompt=prompt_text,
            aspect_ratio="9:16",
            loop=False
        )
        task_id = generation.id
        print(f"Luma Task Submitted. Task ID: {task_id}")

        # Polling loop for completion
        while True:
            time.sleep(10)
            status_obj = luma_client.generations.get(id=task_id)
            state = status_obj.state
            print(f"Luma Generation Status: {state}")

            if state == "completed":
                video_url = status_obj.assets.video
                print(f"Downloading Luma Video from: {video_url}")
                res = requests.get(video_url)
                if res.status_code == 200:
                    with open(output_video, "wb") as f:
                        f.write(res.content)
                    return output_video
                break
            elif state == "failed":
                print(f"Luma Generation Failed: {status_obj.failure_reason}")
                return None

    except Exception as e:
        print(f"Luma API Error: {e}")
        return None


def generate_video_kling(prompt_text, output_video="ai_kling_video.mp4"):
    """Kling AI Video API Fallback Integration"""
    if not KLING_API_KEY:
        print("Kling API Key Missing.")
        return None

    print("Submitting Kling AI Video Generation Task...")
    url = "https://api.klingai.com/v1/videos/text2video"
    headers = {
        "Authorization": f"Bearer {KLING_API_KEY}",
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
            print(f"Kling Error: {data}")
            return None

        task_id = data["data"]["task_id"]
        print(f"Kling Task ID: {task_id}")

        # Polling
        task_url = f"https://api.klingai.com/v1/videos/text2video/{task_id}"
        while True:
            time.sleep(10)
            poll_res = requests.get(task_url, headers=headers).json()
            status = poll_res.get("data", {}).get("task_status")
            print(f"Kling Task Status: {status}")

            if status == "succeed":
                video_url = poll_res["data"]["task_result"]["videos"][0]["url"]
                v_res = requests.get(video_url)
                with open(output_video, "wb") as f:
                    f.write(v_res.content)
                return output_video
            elif status == "failed":
                return None

    except Exception as e:
        print(f"Kling API Error: {e}")
        return None


def merge_video_audio(video_file, audio_file, final_output="final_short.mp4"):
    """FFmpeg Syncing"""
    print("Syncing AI Video & Audio via FFmpeg...")
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
        print(f"SUCCESS: Video generated at '{final_output}'")
        return final_output
    else:
        print(f"FFmpeg Error: {result.stderr.decode('utf-8')}")
        return None


# ==========================================
# 3. MAIN EXECUTION PIPELINE
# ==========================================
if __name__ == "__main__":
    print("=== YouTube Shorts AI Video Automation Started ===")

    script_text = generate_script()
    audio_path = generate_audio(script_text)

    # Short ke exact style ke liye 3D Vegetable Funeral / Crying Prompt
    prompt = (
        "3D Pixar style cinematic video of cute animated vegetables (onion, carrot, potato, pumpkin) "
        "crying and walking together in a rural Indian village street, detailed character expressions, "
        "dramatic emotional lighting, 4k resolution, vertical 9:16 short video."
    )

    # Step 1: Luma AI Try karein
    generated_video = generate_video_luma(prompt)

    # Step 2: Agar Luma na chale toh Kling AI Fallback
    if not generated_video:
        print("Falling back to Kling AI API...")
        generated_video = generate_video_kling(prompt)

    if generated_video and audio_path:
        merge_video_audio(generated_video, audio_path)
    else:
        print("Video Generation Failed from both Luma & Kling APIs.")
