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


def generate_topic_and_script():
    """Generates a dynamic unique topic + long script (30-60 secs) via Gemini"""
    print("Selecting Dynamic Topic & Script via Gemini...")
    
    # Fallback topics in case API fails
    fallback_topics = [
        "A 3D animated crying onion who complains people cry when cutting him",
        "A 3D animated angry red chilli warning people not to eat him",
        "A 3D animated melting ice cream scared of the hot summer sun",
        "A 3D animated chai cup complaining people sip him too fast",
        "A 3D animated sad potato who wants to be famous fries",
        "A 3D animated dramatic mango boasting he is the king of fruits",
        "A 3D animated smartphone complaining it gets used all night"
    ]
    
    selected_topic = random.choice(fallback_topics)
    default_script = "ओ यारों, आज मेरा दिल बहुत उदास है! सब मुझे देखकर हंसते हैं, पर मेरा दर्द कोई नहीं समझता. काश कोई मेरी भी बात सुने!"

    if not gemini_client:
        return selected_topic, default_script

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    
    prompt_text = (
        "You are a viral YouTube Shorts creator. Choose 1 funny, unique, dramatic, 3D animated character topic "
        "(like crying onion, angry chilli, melting ice cream, dramatic mango, stressed chai cup, etc.). "
        "Then write a 40 to 60 words dramatic emotional funny monologue dialogue in Hindi spoken by that character. "
        "The dialogue should take around 30 to 45 seconds to speak out loud.\n\n"
        "STRICT OUTPUT FORMAT:\n"
        "TOPIC: [Visual prompt description of the 3D animated character in English]\n"
        "SCRIPT: [Hindi dialogue text only]"
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
                script_part = parts[1].strip().replace('*', '').replace('"', '').strip()
                
                print(f"--- New Topic Generated --- \n{topic_part}")
                print(f"--- Script Generated --- \n{script_part}")
                return topic_part, script_part
            else:
                # If Gemini gave plain script without format label
                script_part = raw_text.replace('*', '').replace('"', '').strip()
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
    """Dynamic 3D Visual Engine for any character (30-60 second video)"""
    print(f"Generating 3D AI Visual for Topic: {visual_prompt}...")
    seed = random.randint(10000, 999999)
    
    clean_prompt = f"3D Pixar style animated {visual_prompt}, highly detailed, cute expressive face, dramatic lighting, 9:16 vertical 4k"
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

            # Duration set to 60 seconds max (1500 frames @ 25fps) with smooth slow zoom
            ffmpeg_cmd = [
                "ffmpeg",
                "-loop", "1",
                "-i", temp_img,
                "-vf", "scale=720:1280,zoompan=z='min(zoom+0.0004,1.15)':d=1500:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=720x1280",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-r", "25",
                "-t", "60",
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
