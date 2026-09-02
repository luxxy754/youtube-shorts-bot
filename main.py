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

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

gemini_client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Warning: {e}")


def generate_script():
    """YouTube Shorts Style Script Generation"""
    print("Generating Hindi Script via Gemini...")
    if not gemini_client:
        return "ओ यारों, मेरा यार ना रहा मेरा!"

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    prompt_text = (
        "Write 1 dramatic emotional funny dialog in Hindi spoken by a crying 3D animated onion. "
        "Strictly write only the Hindi dialogue text, under 8 words."
    )

    for model_name in models_to_try:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt_text
            )
            script_text = response.text.strip()
            script_text = script_text.replace('*', '').replace('"', '').strip()
            print(f"Generated Script: {script_text}")
            return script_text
        except Exception as e:
            print(f"Gemini Error ({model_name}): {e}")

    return "ओ यारों, मेरा यार ना रहा मेरा!"


def generate_audio(text, output_file="hindi_audio.mp3"):
    """Voiceover Generation using gTTS"""
    print("Generating Hindi Voiceover...")
    tts = gTTS(text=text, lang="hi", slow=False)
    tts.save(output_file)
    print(f"Audio saved to: {output_file}")
    return output_file


def generate_video_free_pollinations(prompt_text, output_video="ai_video.mp4"):
    """Stable 3D AI Visual Engine"""
    print("Generating 3D AI Visual via Pollinations Engine...")
    seed = random.randint(10000, 999999)
    
    # Shortened and cleaned prompt to prevent HTTP 500 server errors
    clean_prompt = "3D Pixar style animated crying onion character, big teary eyes, weeping, dramatic emotional face, 9:16 vertical 4k"
    encoded_prompt = requests.utils.quote(clean_prompt)
    
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=720&height=1280&seed={seed}&nologo=true&model=pixart"

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(image_url, headers=headers, timeout=60)
        
        if res.status_code == 200:
            temp_img = "temp_scene.jpg"
            with open(temp_img, "wb") as f:
                f.write(res.content)
            print(f"AI Visual generated successfully: {temp_img}")

            # FFmpeg Command to convert 3D Render into Motion Short Video
            ffmpeg_cmd = [
                "ffmpeg",
                "-loop", "1",
                "-i", temp_img,
                "-vf", "zoompan=z='min(zoom+0.0015,1.15)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=720x1280",
                "-c:v", "libx264",
                "-t", "5",
                "-pix_fmt", "yuv420p",
                "-y",
                output_video
            ]
            subprocess.run(ffmpeg_cmd, check=True)
            return output_video
        else:
            print(f"Pollinations HTTP Error: {res.status_code}")
            return None
    except Exception as e:
        print(f"Visual Generation Exception: {e}")
        return None


def merge_video_audio(video_file, audio_file, final_output="final_short.mp4"):
    """FFmpeg Syncing Video & Voiceover"""
    print("Merging Video & Voiceover via FFmpeg...")
    
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
        print(f"FFmpeg Error: {result.stderr.decode('utf-8')}")
        return None


if __name__ == "__main__":
    print("=== YouTube Shorts AI Automation Pipeline Started ===")

    script_text = generate_script()
    audio_path = generate_audio(script_text)

    prompt = "3D Pixar style animated crying onion character"

    generated_video = generate_video_free_pollinations(prompt)

    if generated_video and audio_path:
        final_video = merge_video_audio(generated_video, audio_path)
        if final_video:
            print("\n=== Automation Finished Successfully! ===")
        else:
            print("\n=== Syncing Failed ===")
    else:
        print("\n=== Pipeline Failed at Generation Step ===")
