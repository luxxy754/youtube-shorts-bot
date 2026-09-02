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
    print("Warning: google-genai module not installed.")

# ==========================================
# 1. API KEYS SETUP
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Client Init Warning: {e}")


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def generate_script():
    """Gemini AI se Script Generate Karna"""
    print("Generating Script via Gemini...")
    if not client:
        return "आज का ज्ञान: डायमंड खरीदो या सब्जी, एटीट्यूड भारी होना चाहिए!"

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    prompt_text = "Write a super short, 1-line funny Hindi quote for a YouTube Short about luxury jewelry or funny vegetables. Under 10 words."

    for model_name in models_to_try:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt_text
                )
                script_text = response.text.strip()
                print(f"Generated Script: {script_text}")
                return script_text
            except Exception as e:
                print(f"Gemini Error ({model_name}): {e}")
                time.sleep(2)

    return "आज का ज्ञान: डायमंड खरीदो या सब्जी, एटीट्यूड भारी होना चाहिए!"


def generate_audio(text, output_file="hindi_audio.mp3"):
    """gTTS Audio Generation"""
    print("Generating Hindi Audio via gTTS...")
    tts = gTTS(text=text, lang="hi", slow=False)
    tts.save(output_file)
    print(f"Audio saved to: {output_file}")
    return output_file


def download_ai_image(output_image="character.jpg"):
    """Pollinations AI High-Quality Image Download"""
    print("Downloading AI Trending Image...")
    trending_prompts = [
        "Incredible Hulk wearing massive sparkling black diamond chain and luxury Rolex watch, cinematic lighting, 4k, hyperrealistic",
        "Funny cute 3d talking carrot with big animated eyes, pixar style, vibrant colors, 4k",
        "Muscular Hulk adorned in rich iced out platinum diamond necklace, cinematic lighting"
    ]
    chosen_prompt = random.choice(trending_prompts)
    print(f"Prompt: {chosen_prompt}")
    
    seed = random.randint(1000, 99999)
    image_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(chosen_prompt)}?width=720&height=1280&seed={seed}&nologo=true"
    
    res = requests.get(image_url, timeout=30)
    if res.status_code == 200:
        with open(output_image, "wb") as f:
            f.write(res.content)
        print(f"Image saved to: {output_image}")
        return output_image
    else:
        print(f"Failed to download image. Status: {res.status_code}")
        return None


def create_short_video_ffmpeg(image_path, audio_path, output_video="final_short.mp4"):
    """FFmpeg optimized Video creation"""
    print("Generating Short Video via FFmpeg...")
    try:
        command = [
            "ffmpeg",
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-y",
            output_video
        ]
        
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            print(f"SUCCESS: Short Video generated at '{output_video}'")
            return output_video
        else:
            print(f"FFmpeg Error: {result.stderr.decode('utf-8')}")
            return None
    except Exception as e:
        print(f"FFmpeg Exception: {e}")
        return None


# ==========================================
# 3. MAIN EXECUTION PIPELINE
# ==========================================
if __name__ == "__main__":
    print("=== YouTube Shorts Automation Bot Started ===")

    script_text = generate_script()
    audio_path = generate_audio(script_text)
    image_path = download_ai_image()

    if image_path and audio_path:
        final_video = create_short_video_ffmpeg(image_path, audio_path)
        if final_video:
            print("\n=== Workflow Completed Successfully! ===")
        else:
            print("\n=== Workflow Failed at FFmpeg Step ===")
    else:
        print("\n=== Workflow Failed at Image/Audio Generation ===")
