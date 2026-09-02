import os
import time
import random
import requests
import subprocess
from gTTS import gTTS

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
        "Strictly write only the Hindi dialogue text (in Devnagari or Hinglish), under 10 words. "
        "Example: ओ यारों, मेरा यार ना रहा मेरा!"
    )

    for model_name in models_to_try:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt_text
            )
            script_text = response.text.strip()
            # Clean unwanted text
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
    """3D Video Generation via Free Engine"""
    print("Generating 3D AI Video via Pollinations Engine...")
    seed = random.randint(10000, 999999)
    encoded_prompt = requests.utils.quote(prompt_text)
    
    # 3D Animation Video Request
    video_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=720&height=1280&model=flux&seed={seed}&nologo=true"

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(video_url, headers=headers, stream=True, timeout=120)
        
        if res.status_code == 200:
            with open(output_video, "wb") as f:
                for chunk in res.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
            print(f"AI Video downloaded successfully: {output_video}")
            return output_video
        else:
            print(f"Pollinations Video Engine HTTP Error: {res.status_code}")
            return None
    except Exception as e:
        print(f"Video Generation Exception: {e}")
        return None


def merge_video_audio(video_file, audio_file, final_output="final_short.mp4"):
    """FFmpeg Syncing & Looping Video to Match Audio Length"""
    print("Merging Video & Voiceover via FFmpeg...")
    
    # FFmpeg command to loop video seamlessly and match voice duration
    command = [
        "ffmpeg",
        "-ignore_loop", "0",
        "-i", video_file,
        "-i", audio_file,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-y",
        final_output
    ]
    
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        print(f"SUCCESS: Final Short Video created at '{final_output}'")
        return final_output
    else:
        # Fallback simpler copy command if libx264 re-encode fails
        print("Retrying FFmpeg basic stream merge...")
        fallback_cmd = [
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
        res_fb = subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res_fb.returncode == 0:
            print(f"SUCCESS: Final Short Video created at '{final_output}'")
            return final_output
        else:
            print(f"FFmpeg Error: {res_fb.stderr.decode('utf-8')}")
            return None


if __name__ == "__main__":
    print("=== YouTube Shorts AI Automation Pipeline Started ===")

    # Step 1: Dialogue
    script_text = generate_script()
    
    # Step 2: Voiceover
    audio_path = generate_audio(script_text)

    # Step 3: Exact 3D Crying Vegetables Prompt (Like the YouTube Short)
    video_prompt = (
        "3D Pixar style cinematic video of cute animated 3D crying onion character with big teary eyes, "
        "dramatic emotional weeping face expression, talking and crying, rural village background, "
        "9:16 vertical short format, highly detailed 3D animation"
    )

    # Step 4: AI Video Generation
    generated_video = generate_video_free_pollinations(video_prompt)

    # Step 5: Merge Video + Audio
    if generated_video and audio_path:
        final_video = merge_video_audio(generated_video, audio_path)
        if final_video:
            print("\n=== Automation Finished Successfully! ===")
        else:
            print("\n=== Syncing Failed ===")
    else:
        print("\n=== Pipeline Failed at Generation Step ===")
