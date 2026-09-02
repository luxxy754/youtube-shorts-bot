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


def generate_story_script():
    """Generates a 3-Scene Hindi Animated Story Script via Gemini"""
    print("Generating Multi-Scene Animated Story Script via Gemini...")

    default_data = {
        "character": "3D Pixar animated cute Aalu character",
        "scenes": [
            {"prompt": "3D Pixar style animated Aalu character looking confused in a market", "script": "ओ यारों, आज मैं नया कारोबार शुरू करने निकला हूँ!"},
            {"prompt": "3D Pixar style animated angry Baingan character staring fiercely", "script": "अरे बैंगन भाई, तुम मुझसे इतना जलते क्यों हो?"},
            {"prompt": "3D Pixar style animated Aalu character celebrating happily", "script": "मेहनत का फल मीठा होता है, अब मेरा काम चल पड़ा!"}
        ]
    }

    if not gemini_client:
        return default_data

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    prompt_text = (
        "Create a funny 3-scene animated Hindi short story starring 3D veggie characters like Aalu, Baingan, Gajar, Chilli. "
        "Each scene must have a short visual image description in English (max 6 words) and 1 pure Hindi dialogue line (under 10 words). "
        "Do NOT use brackets or stage directions.\n\n"
        "STRICT FORMAT:\n"
        "SCENE 1 IMAGE: [3D Pixar animated character visual prompt]\n"
        "SCENE 1 SCRIPT: [Hindi dialogue line]\n"
        "SCENE 2 IMAGE: [3D Pixar animated character visual prompt]\n"
        "SCENE 2 SCRIPT: [Hindi dialogue line]\n"
        "SCENE 3 IMAGE: [3D Pixar animated character visual prompt]\n"
        "SCENE 3 SCRIPT: [Hindi dialogue line]"
    )

    for model_name in models_to_try:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt_text
            )
            raw_text = response.text.strip()
            
            scenes = []
            img_prompts = re.findall(r'SCENE \d+ IMAGE:\s*(.*)', raw_text)
            scripts = re.findall(r'SCENE \d+ SCRIPT:\s*(.*)', raw_text)

            if len(img_prompts) >= 3 and len(scripts) >= 3:
                for i in range(3):
                    clean_script = re.sub(r'\(.*?\)', '', scripts[i]).replace('*', '').replace('"', '').strip()
                    clean_prompt = " ".join(img_prompts[i].split()[:8])
                    scenes.append({"prompt": clean_prompt, "script": clean_script})
                return {"scenes": scenes}

        except Exception as e:
            print(f"Gemini Story Error ({model_name}): {e}")

    return default_data


def generate_audio_segments(scenes):
    """Generates audio for each scene and returns file list"""
    audio_files = []
    print("Generating Hindi Voiceovers for Scenes...")
    for idx, scene in enumerate(scenes):
        out_file = f"audio_scene_{idx}.mp3"
        tts = gTTS(text=scene["script"], lang="hi", slow=False)
        tts.save(out_file)
        audio_files.append(out_file)
    return audio_files


def download_scene_image(visual_prompt, idx):
    """Downloads 3D Image for a Scene"""
    seed = random.randint(10000, 999999)
    clean_prompt = f"3D Pixar style {visual_prompt}, highly detailed, vertical 9:16"
    encoded_prompt = requests.utils.quote(clean_prompt)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=720&height=1280&seed={seed}&nologo=true&model=pixart"

    try:
        res = requests.get(image_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=60)
        if res.status_code == 200:
            img_path = f"scene_{idx}.jpg"
            with open(img_path, "wb") as f:
                f.write(res.content)
            return img_path
    except Exception as e:
        print(f"Image Download Exception: {e}")
    return None


def create_scene_videos(scenes, audio_files):
    """Renders small MP4 videos for each scene using FFmpeg"""
    scene_videos = []
    print("Rendering Scene Video Clips...")

    for idx, scene in enumerate(scenes):
        img_path = download_scene_image(scene["prompt"], idx)
        audio_path = audio_files[idx]
        output_clip = f"clip_{idx}.mp4"

        if img_path and os.path.exists(audio_path):
            # Render video clip synced exactly to the scene audio duration
            ffmpeg_cmd = [
                "ffmpeg",
                "-loop", "1",
                "-i", img_path,
                "-i", audio_path,
                "-vf", "scale=720:1280,zoompan=z='min(zoom+0.0015,1.12)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=720x1280",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "28",
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                "-pix_fmt", "yuv420p",
                "-y",
                output_clip
            ]
            subprocess.run(ffmpeg_cmd, check=True)
            scene_videos.append(output_clip)

    return scene_videos


def merge_all_scenes(scene_videos, final_output="final_short.mp4"):
    """Concatenates all scene clips into a single YouTube Short"""
    print("Merging All Scenes into Final Story Short...")
    
    # Create list file for FFmpeg concat
    with open("files.txt", "w") as f:
        for vid in scene_videos:
            f.write(f"file '{vid}'\n")

    concat_cmd = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", "files.txt",
        "-c", "copy",
        "-y",
        final_output
    ]
    
    result = subprocess.run(concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        print(f"SUCCESS: Final Multi-Scene Story Video generated: {final_output}")
        return final_output
    else:
        print(f"Merge Error: {result.stderr.decode('utf-8')}")
        return None


if __name__ == "__main__":
    print("=== Multi-Scene Animated Story Bot Started ===")

    # Step 1: Script
    story_data = generate_story_script()
    scenes = story_data["scenes"]

    # Step 2: Audio
    audio_files = generate_audio_segments(scenes)

    # Step 3: Render Scene Clips
    video_clips = create_scene_videos(scenes, audio_files)

    # Step 4: Final Merge
    if video_clips:
        final_video = merge_all_scenes(video_clips)
        if final_video:
            print("\n=== Automation Finished Successfully! ===")
        else:
            print("\n=== Merging Failed ===")
    else:
        print("\n=== Scene Generation Failed ===")
