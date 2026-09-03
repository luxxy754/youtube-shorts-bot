import os
import re
import sys
import time
import requests
import subprocess
from gtts import gTTS

# Gemini Setup
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ELEVEN_KEY = os.getenv("ELEVEN_KEY_1") or os.getenv("ELEVEN_KEY_2") or ""

# PixVerse API Keys Fallback List
PIXVERSE_KEYS = [
    os.getenv("PIXVERSE_API_KEY_1", ""),
    os.getenv("PIXVERSE_API_KEY_2", ""),
    os.getenv("PIXVERSE_API_KEY_3", ""),
    os.getenv("PIXVERSE_API_KEY_4", "")
]
# Clean empty keys
PIXVERSE_KEYS = [k for k in PIXVERSE_KEYS if k.strip()]

gemini_client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Warning: {e}")
else:
    if not GEMINI_AVAILABLE:
        print("WARNING: google-genai package not installed, using default script.")
    if not GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY not set, using default script.")


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
        print("Gemini client not available, falling back to default script.")
        return default_data

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest"]
    prompt_text = (
        "Create a funny 2-scene animated Hindi short story starring 3D cartoon veggies. "
        "Each scene must have a visual video prompt in English describing action/motion (max 12 words) and 1 pure Hindi dialogue line.\n\n"
        "STRICT FORMAT:\n"
        "SCENE 1 PROMPT: [Video prompt]\n"
        "SCENE 1 SCRIPT: [Hindi dialogue line]\n"
        "SCENE 2 PROMPT: [Video prompt]\n"
        "SCENE 2 SCRIPT: [Hindi dialogue line]"
    )

    for model_name in models_to_try:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt_text
            )
            raw_text = (response.text or "").strip()

            scenes = []
            video_prompts = re.findall(r'SCENE \d+ PROMPT:\s*(.*)', raw_text)
            scripts = re.findall(r'SCENE \d+ SCRIPT:\s*(.*)', raw_text)

            if len(video_prompts) >= 2 and len(scripts) >= 2:
                for i in range(2):
                    clean_script = re.sub(r'\(.*?\)', '', scripts[i]).replace('*', '').replace('"', '').strip()
                    clean_prompt = video_prompts[i].strip() + ", 3D animated Pixar style, 9:16 vertical video"
                    if clean_script and clean_prompt:
                        scenes.append({"prompt": clean_prompt, "script": clean_script})
                if len(scenes) == 2:
                    print(f"Story generated successfully using {model_name}.")
                    return {"scenes": scenes}
                print(f"Gemini ({model_name}) returned incomplete scenes, trying next model...")
            else:
                print(f"Gemini ({model_name}) output did not match expected format, trying next model...")

        except Exception as e:
            print(f"Gemini Story Error ({model_name}): {e}")

    print("All Gemini models failed, falling back to default script.")
    return default_data


def generate_video_pixverse_single_key(api_key, prompt_text, idx):
    """Tries video generation with one specific PixVerse API Key"""
    headers = {
        "API-KEY": api_key,
        "Content-Type": "application/json"
    }

    url = "https://api.pixverse.ai/v1/video/text"
    payload = {
        "prompt": prompt_text,
        "aspect_ratio": "9:16",
        "quality": "540p",
        "duration": 5
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.exceptions.RequestException as e:
        print(f"PixVerse Request Failed (network/timeout): {e}")
        return None

    if res.status_code != 200:
        print(f"PixVerse API HTTP Error {res.status_code}: {res.text[:500]}")
        return None

    try:
        data = res.json()
    except ValueError:
        print(f"PixVerse API returned non-JSON response: {res.text[:500]}")
        return None

    if not (data.get("code") == 0 or "video_id" in str(data)):
        print(f"PixVerse API Error Response: {data}")
        return None

    video_id = data.get("data", {}).get("video_id") or data.get("video_id")
    if not video_id:
        print(f"PixVerse response did not contain a video_id: {data}")
        return None

    print(f"PixVerse Video ID Created: {video_id}. Polling for render...")

    poll_url = f"https://api.pixverse.ai/v1/video/result/{video_id}"
    for attempt in range(40):
        time.sleep(10)
        try:
            status_res = requests.get(poll_url, headers=headers, timeout=30)
            status_res.raise_for_status()
            status_data = status_res.json()
        except requests.exceptions.RequestException as e:
            print(f"PixVerse Poll Request Failed (attempt {attempt + 1}/40): {e}")
            continue
        except ValueError:
            print(f"PixVerse Poll returned non-JSON response (attempt {attempt + 1}/40)")
            continue

        status = status_data.get("data", {}).get("status") or status_data.get("status")

        if status in ["succeeded", "success", 1]:
            video_url = status_data.get("data", {}).get("url") or status_data.get("url")
            if not video_url:
                print(f"PixVerse marked succeeded but no URL found: {status_data}")
                return None
            try:
                vid_bytes = requests.get(video_url, timeout=60).content
            except requests.exceptions.RequestException as e:
                print(f"Failed to download rendered PixVerse video: {e}")
                return None
            out_file = f"pixverse_scene_{idx}.mp4"
            with open(out_file, "wb") as f:
                f.write(vid_bytes)
            print(f"Scene {idx + 1} video rendered successfully via PixVerse!")
            return out_file
        elif status in ["failed", "error", -1]:
            print(f"PixVerse Rendering Failed: {status_data}")
            return None
        # else: still processing, keep polling

    print(f"PixVerse polling timed out after 40 attempts for video_id {video_id}")
    return None


def generate_video_pixverse(prompt_text, idx):
    """Loops through all available PixVerse Keys until one succeeds"""
    if not PIXVERSE_KEYS:
        print("ERROR: No PixVerse Keys found in GitHub Secrets! "
              "Set PIXVERSE_API_KEY_1 (and optionally _2/_3/_4) as repo secrets.")
        return None

    for key_idx, key in enumerate(PIXVERSE_KEYS):
        print(f"Attempting PixVerse Generation using Key #{key_idx + 1}...")
        out_file = generate_video_pixverse_single_key(key, prompt_text, idx)
        if out_file:
            return out_file
        print(f"Key #{key_idx + 1} failed or ran out of credits. Trying next key...")

    return None


def assemble_scene(video_file, script_text, idx):
    """Syncs Audio with PixVerse Video"""
    audio_file = f"audio_{idx}.mp3"

    eleven_success = False
    if ELEVEN_KEY:
        try:
            url = "https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB"
            headers = {"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"}
            payload = {
                "text": script_text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {"stability": 0.35, "similarity_boost": 0.85}
            }
            res = requests.post(url, json=payload, headers=headers, timeout=20)
            if res.status_code == 200 and res.content:
                with open(audio_file, "wb") as f:
                    f.write(res.content)
                eleven_success = True
            else:
                print(f"ElevenLabs API Error {res.status_code}: {res.text[:300]}")
        except requests.exceptions.RequestException as e:
            print(f"ElevenLabs Error: {e}")

    if not eleven_success:
        try:
            tts = gTTS(text=script_text, lang="hi", slow=False)
            tts.save(audio_file)
        except Exception as e:
            print(f"gTTS fallback failed too: {e}")
            raise

    output_clip = f"clip_{idx}.mp4"
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", video_file,
        "-i", audio_file,
        "-filter_complex", "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v]",
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        "-y",
        output_clip
    ]
    try:
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg failed while assembling scene {idx}:\n{e.stderr}")
        raise
    return output_clip


def merge_clips(clip_files, final_output="final_short.mp4"):
    """Merges all video clips into one Short"""
    with open("files.txt", "w") as f:
        for clip in clip_files:
            f.write(f"file '{clip}'\n")

    concat_cmd = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", "files.txt",
        "-c", "copy",
        "-y",
        final_output
    ]
    try:
        subprocess.run(concat_cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg failed while merging clips:\n{e.stderr}")
        raise
    return final_output


if __name__ == "__main__":
    print("=== Fully Automated PixVerse 4-Key Bot Started ===")

    story = generate_story_script()
    scenes = story["scenes"]
    final_clips = []

    for idx, scene in enumerate(scenes):
        print(f"\n--- Processing Scene {idx + 1} ---")
        try:
            raw_video = generate_video_pixverse(scene["prompt"], idx)
            if raw_video:
                clip = assemble_scene(raw_video, scene["script"], idx)
                final_clips.append(clip)
            else:
                print(f"Scene {idx + 1} skipped: no video was generated.")
        except Exception as e:
            print(f"Scene {idx + 1} failed with an unexpected error: {e}")

    if final_clips:
        try:
            final_video = merge_clips(final_clips)
        except Exception as e:
            print(f"\nFAILED: Could not merge clips into final video: {e}")
            sys.exit(1)
        print(f"\nSUCCESS: Fully Automated PixVerse Short Ready: {final_video}")
    else:
        print("\nFAILED: Video generation unsuccessful. No clips were produced "
              "(check PixVerse key validity/credits and API responses above).")
        sys.exit(1)
