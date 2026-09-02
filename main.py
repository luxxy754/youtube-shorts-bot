import os
import re
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


def generate_topic_and_script():
    """Generates a dynamic unique short topic + clean long script via Gemini"""
    print("Selecting Dynamic Topic & Script via Gemini...")
    
    fallback_topics = [
        "animated crying onion character",
        "animated angry red chilli character",
        "animated melting ice cream character",
        "animated scared pressure cooker character",
        "animated sad potato character",
        "animated dramatic mango character"
    ]
    
    selected_topic = random.choice(fallback_topics)
    default_script = "ओ यारों, आज मेरा दिल बहुत उदास है! सब मुझे देखकर हंसते हैं, पर मेरा दर्द कोई नहीं समझता. काश कोई मेरी भी बात सुने!"

    if not gemini_client:
        return selected_topic, default_script

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    
    prompt_text = (
        "You are a viral YouTube Shorts creator. Choose 1 funny 3D animated character topic. "
        "Write a 40 to 60 words dramatic emotional dialogue in pure Hindi script for the character. "
        "Do NOT include any stage directions, English words, or text in brackets like (crying) or (sighs).\n\n"
        "STRICT OUTPUT FORMAT:\n"
        "TOPIC: [3 to 5 words max English visual description, e.g. 3D animated anxious pressure cooker]\n"
        "SCRIPT: [Pure Hindi dialogue text only]"
    )

    for model_name in models_to_try:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt_text
            )
            raw_text = response.text.strip()
            
            if "TOPIC:" in raw_text and "SCRIPT:" in raw_text:
                parts = raw_text.split("SCRIPT:")
                topic_part = parts[0].replace("TOPIC:", "").strip()
                script_part = parts[1].strip()
                
                # Clean brackets/parentheses and extra markup from script
                script_part = re.sub(r'\(.*?\)', '', script_part)
                script_part = re.sub(r'\[.*?\]', '', script_part)
                script_part = script_part.replace('*', '').replace('"', '').strip()
                
                # Keep topic short (max 10 words) to avoid HTTP 500 error
                topic_part = " ".join(topic_part.split()[:10])
                
                print(f"--- New Clean Topic --- \n{topic_part}")
                print(f"--- Clean Script --- \n{script_part}")
                return topic_part, script_part
            else:
                script_part = re.sub(r'\(.*?\)', '', raw_text)
                script_part = script_part.replace('*', '').replace('"', '').strip()
                return selected_topic, script_part
                
        except Exception as e:
            print(f"Gemini Error ({model_name}): {e}")

    return selected_topic, default_script


def generate_audio(text, output_file="hindi_audio.mp3"):
    """Voiceover Generation using gTTS"""
    print("Generating Hindi Voiceover...")
    tts = gTTS(text=text, lang="hi", slow=False)
    tts.save(output_file)
    print(f"Audio saved to: {output_file}")
    return output_file


def generate_video_free_pollinations(visual_prompt, output_video="ai_video.mp4"):
    """Optimized Fast & Small File Size Video Engine"""
    print(f"Generating 3D AI Visual for Topic: {visual_prompt}...")
    seed = random.randint(10000, 999999)
    
    clean_prompt = f"3D Pixar style {visual_prompt}, highly detailed, cute expressive character, 9:16 vertical 4k"
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

            # Lightweight encoding settings: CRF 28 & ultrafast preset for tiny file size
            ffmpeg_cmd = [
                "ffmpeg",
                "-loop", "1",
                "-i", temp_img,
                "-vf", "scale=720:1280,zoompan=z='min(zoom+0.001,1.15)':d=750:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=720x1280",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "28",
                "-r", "25",
                "-t", "45",
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
    """FFmpeg Syncing Video & Voiceover dynamically based on audio length"""
    print("Merging Video & Voiceover via FFmpeg...")
    
    command = [
        "ffmpeg",
        "-stream_loop", "-1",
        "-i", video_file,
        "-i", audio_file,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
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
    print("=== Dynamic Trending YouTube Shorts Bot Started ===")

    # Step 1: Generate dynamic topic and script
    topic_prompt, script_text = generate_topic_and_script()
    
    # Step 2: Generate Audio
    audio_path = generate_audio(script_text)

    # Step 3: Generate matching 3D Video
    generated_video = generate_video_free_pollinations(topic_prompt)

    # Step 4: Sync & Output
    if generated_video and audio_path:
        final_video = merge_video_audio(generated_video, audio_path)
        if final_video:
            print("\n=== Automation Finished Successfully! ===")
        else:
            print("\n=== Syncing Failed ===")
    else:
        print("\n=== Pipeline Failed at Generation Step ===")
