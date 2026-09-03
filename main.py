import os
import re
import time
import requests
import subprocess
from gtts import gTTS

# Replicate SDK Setup
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    REPLICATE_AVAILABLE = False

# Gemini SDK Setup
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
ELEVEN_KEY = os.getenv("ELEVEN_KEY_1") or os.getenv("ELEVEN_KEY_2") or ""

gemini_client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Warning: {e}")


def generate_story_script():
    """Generates 2-Scene Story Script via Gemini"""
    print("Generating Story Script via Gemini...")

    default_data = {
        "scenes": [
            {
                "prompt": "3D Pixar style animated cute potato character talking dynamically in colorful market",
                "script": "ओ यारों, आज मैं नया कारोबार शुरू करने निकला हूँ!"
            },
            {
                "prompt": "3D Pixar style animated angry eggplant character shouting furiously",
                "script": "अरे बैंगन भाई, तुम मुझसे इतना जलते क्यों हो?"
            }
        ]
    }

    if not gemini_client:
        return default_data

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash"]
    prompt_text = (
        "Create a funny 2-scene animated Hindi short story starring 3D cartoon veggies. "
        "Each scene must have a visual prompt in English describing action/motion (max 12 words) and 1 pure Hindi dialogue line.\n\n"
        "STRICT FORMAT:\n"
        "SCENE 1 PROMPT: [Visual prompt]\n"
        "SCENE 1 SCRIPT: [Hindi dialogue line]\n"
        "SCENE 2 PROMPT: [Visual prompt]\n"
        "SCENE 2 SCRIPT: [Hindi dialogue line]"
    )

    for model_name in models_to_try:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt_text
            )
            raw_text = response.text.strip()
            
            scenes = []
            video_prompts = re.findall(r'SCENE \d+ PROMPT:\s*(.*)', raw_text)
            scripts = re.findall(r'SCENE \d+ SCRIPT:\s*(.*)', raw_text)

            if len(video_prompts) >= 2 and len(scripts) >= 2:
                for i in range(2):
                    clean_script = re.sub(r'\(.*?\)', '', scripts[i]).replace('*', '').replace('"', '').strip()
                    clean_prompt = video_prompts[i].strip() + ", 3D Pixar animated style, 9:16 vertical short"
                    scenes.append({"prompt": clean_prompt, "script": clean_script})
                return {"scenes": scenes}

        except Exception as e:
            print(f"Gemini Story Error ({model_name}): {e}")

    return default_data


def generate_video_replicate(prompt_text, idx):
    """Generates Video using Replicate API"""
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN:
        print("Replicate Token not found, skipping Replicate...")
        return None

    print(f"Generating Scene {idx+1} Video via Replicate...")
    try:
        # Stable Video Generation Model
        output = replicate.run(
            "stability-ai/stable-diffusion-animation:2d71891eab0e04918f0808a3d53b47f7d1421cbeedc534c09d5718ebcb2f9dd2",
            input={"prompt": prompt_text, "max_frames": 40}
        )
        
        video_url = None
        if isinstance(output, list) and len(output) > 0:
            video_url = output[0]
        elif isinstance(output, str):
            video_url = output

        if video_url:
            vid_bytes = requests.get(video_url, timeout=60).content
            out_file = f"replicate_scene_{idx}.mp4"
            with open(out_file, "wb") as f:
                f.write(vid_bytes)
            print(f"Scene {idx+1} video rendered successfully via Replicate!")
            return out_file
    except Exception as e:
        print(f"Replicate API Error: {e}")

    return None


def generate_fallback_image(prompt_text, idx):
    """Fallback: Generates 9:16 Image via Pollinations (100% Free, Unlimited)"""
    print(f"Generating Fallback High-Res Image for Scene {idx+1}...")
    try:
        clean_prompt = requests.utils.quote(prompt_text)
        url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1080&height=1920&nologo=true"
        res = requests.get(url, timeout=30)
        if res.status_code == 200:
            out_file = f"fallback_scene_{idx}.png"
            with open(out_file, "wb") as f:
                f.write(res.content)
            return out_file
    except Exception as e:
        print(f"Fallback Image Error: {e}")
    return None


def assemble_scene(media_file, script_text, idx):
    """Syncs Voice & Adds Camera Motion Effect"""
    audio_file = f"audio_{idx}.mp3"
    
    # Try ElevenLabs Voice if key is present
    eleven_success = False
    if ELEVEN_KEY:
        try:
            url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
            headers = {"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"}
            payload = {
                "text": script_text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
            }
            res = requests.post(url, json=payload, headers=headers, timeout=20)
            if res.status_code == 200:
                with open(audio_file, "wb") as f:
                    f.write(res.content)
                eleven_success = True
        except Exception as e:
            print(f"ElevenLabs Error: {e}")

    if not eleven_success:
        tts = gTTS(text=script_text, lang="hi", slow=False)
        tts.save(audio_file)

    output_clip = f"clip_{idx}.mp4"

    # Check if media is video or image
    if media_file.endswith(".mp4"):
        ffmpeg_cmd = [
            "ffmpeg", "-i", media_file, "-i", audio_file,
            "-c:v", "copy", "-c:a", "aac",
            "-map", "0:v:0", "-map", "1:a:0",
            "-shortest", "-y", output_clip
        ]
    else:
        # Dynamic Camera Zoom effect for image
        ffmpeg_cmd = [
            "ffmpeg", "-loop", "1", "-i", media_file, "-i", audio_file,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.0015,1.15)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920",
            "-c:v", "libx264", "-t", "5", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", "-y", output_clip
        ]

    subprocess.run(ffmpeg_cmd, check=True)
    return output_clip


def merge_clips(clip_files, final_output="final_short.mp4"):
    """Merges all video clips into one Short"""
    with open("files.txt", "w") as f:
        for clip in clip_files:
            f.write(f"file '{clip}'\n")

    concat_cmd = [
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", "files.txt",
        "-c", "copy", "-y", final_output
    ]
    subprocess.run(concat_cmd, check=True)
    return final_output


if __name__ == "__main__":
    print("=== Automated YouTube Shorts Bot Started ===")

    story = generate_story_script()
    scenes = story["scenes"]
    final_clips = []

    for idx, scene in enumerate(scenes):
        print(f"\n--- Processing Scene {idx+1} ---")
        
        # 1. Try Replicate Video
        media_file = generate_video_replicate(scene["prompt"], idx)
        
        # 2. Unlimited Fallback Option
        if not media_file:
            media_file = generate_fallback_image(scene["prompt"], idx)

        if media_file:
            clip = assemble_scene(media_file, scene["script"], idx)
            final_clips.append(clip)

    if final_clips:
        final_video = merge_clips(final_clips)
        print(f"\nSUCCESS: Fully Automated Video Short Ready: {final_video}")
    else:
        print("\nFAILED: Video generation unsuccessful.")
