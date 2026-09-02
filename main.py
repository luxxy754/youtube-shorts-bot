import os
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
    """Gemini AI se Script generate karne ke liye"""
    print("Generating Hindi Script...")
    if not client:
        return "हां भाई, चाय पी लो पहले, काम तो होता रहेगा!"

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    
    for model_name in models_to_try:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents="Write a very short, funny 1-line joke in Hindi (Devanagari script) for a YouTube Short character. Keep it under 15 words."
                )
                script_text = response.text.strip()
                print(f"Generated Script: {script_text}")
                return script_text
            except Exception as e:
                print(f"Gemini Error ({model_name}): {e}")
                time.sleep(2)
                
    print("Using fallback script.")
    return "हां भाई, चाय पी लो पहले, काम तो होता रहेगा!"


def generate_audio(text, output_file="hindi_audio.mp3"):
    """gTTS ke zariye Audio File generate karne ke liye"""
    print("Generating Hindi Audio via gTTS...")
    tts = gTTS(text=text, lang="hi", slow=False)
    tts.save(output_file)
    print(f"Audio saved to: {output_file}")
    return output_file


def download_character_image(output_image="character.jpg"):
    """Pollinations AI se Direct Image Download"""
    print("Downloading 3D Character Image...")
    prompt = "3d Pixar style funny character, cute male character talking, front facing portrait, high quality"
    image_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=720&height=1280&nologo=true"
    
    res = requests.get(image_url)
    if res.status_code == 200:
        with open(output_image, "wb") as f:
            f.write(res.content)
        print(f"Image saved to: {output_image}")
        return output_image
    else:
        print("Failed to download image.")
        return None


def create_video_with_ffmpeg(image_path, audio_path, output_video="final_short.mp4"):
    """FFmpeg ke zariye Image aur Audio ko Short Video (.mp4) me convert karna"""
    print("Building Short Video with FFmpeg...")
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
            print(f"SUCCESS: Video created at '{output_video}'")
            return output_video
        else:
            print(f"FFmpeg Error: {result.stderr.decode('utf-8')}")
            return None
    except Exception as e:
        print(f"Video Creation Failed: {e}")
        return None


# ==========================================
# 3. MAIN EXECUTION PIPELINE
# ==========================================
if __name__ == "__main__":
    print("=== YouTube Shorts Automation Bot Started ===")

    script_text = generate_script()
    audio_path = generate_audio(script_text)
    image_path = download_character_image()

    if image_path and audio_path:
        video_result = create_video_with_ffmpeg(image_path, audio_path)
        if video_result:
            print("\n=== Workflow Completed Successfully! ===")
        else:
            print("\n=== Workflow Failed at Video Creation ===")
    else:
        print("\n=== Workflow Failed at Media Generation ===")
