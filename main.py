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
    """Gemini AI se Trending Short Script Generate Karna"""
    print("Generating Script via Gemini...")
    if not client:
        return "आज का ज्ञान: डायमंड खरीदो या सब्जी, एटीट्यूड भारी होना चाहिए!"

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    prompt_text = "Write a super short, 1-line viral funny Hindi quote/joke for a YouTube Short about luxury jewelry or funny vegetables. Under 12 words."

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
    """Hindi Audio Generation"""
    print("Generating Hindi Audio via gTTS...")
    tts = gTTS(text=text, lang="hi", slow=False)
    tts.save(output_file)
    print(f"Audio saved to: {output_file}")
    return output_file


def generate_trending_ai_video(output_video="ai_generated_base.mp4"):
    """Pollinations AI Free Unlimited Video Engine"""
    print("Generating Trending AI Video clip...")
    
    # Trending video themes: Hulk with Jewelry or Funny Talking Vegetable
    trending_prompts = [
        "Incredible Hulk wearing massive sparkling black diamond chain and luxury Rolex watch, cinematic lighting, 4k resolution, hyperrealistic, moving character",
        "Funny cute 3d talking carrot with big eyes talking animatedly, pixar style, vibrant colors, photorealistic motion, 4k",
        "Muscular Hulk adorned in rich iced out platinum diamond necklace, flexes in luxury setting, cinematic camera motion, highly detailed"
    ]
    
    chosen_prompt = random.choice(trending_prompts)
    print(f"Selected Prompt: {chosen_prompt}")

    encoded_prompt = requests.utils.quote(chosen_prompt)
    seed = random.randint(1000, 99999)
    video_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=720&height=1280&model=video&seed={seed}&nologo=true"

    print("Requesting video stream from server...")
    res = requests.get(video_url, stream=True)
    if res.status_code == 200:
        with open(output_video, "wb") as f:
            for chunk in res.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
        print(f"Base AI Video saved at: {output_video}")
        return output_video
    else:
        print(f"Video Generation failed with HTTP {res.status_code}")
        return None


def merge_video_and_audio(video_file, audio_file, final_output="final_short.mp4"):
    """FFmpeg Sync for Video & Voiceover"""
    print("Syncing AI Video with Voiceover using FFmpeg...")
    try:
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
            print(f"SUCCESS: Final Short Created at '{final_output}'")
            return final_output
        else:
            print(f"FFmpeg Error: {result.stderr.decode('utf-8')}")
            return None
    except Exception as e:
        print(f"Merge Exception: {e}")
        return None


# ==========================================
# 3. MAIN EXECUTION PIPELINE
# ==========================================
if __name__ == "__main__":
    print("=== Automated Trending Shorts Bot Started ===")

    script_text = generate_script()
    audio_path = generate_audio(script_text)
    base_video_path = generate_trending_ai_video()

    if base_video_path and audio_path:
        final_result = merge_video_and_audio(base_video_path, audio_path)
        if final_result:
            print("\n=== Workflow Completed Successfully! ===")
        else:
            print("\n=== Workflow Failed at Syncing Step ===")
    else:
        print("\n=== Workflow Failed at Generation Step ===")
