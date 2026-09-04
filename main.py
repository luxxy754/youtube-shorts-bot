import os
import re
import sys
import time
import uuid
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

# ElevenLabs keys fallback list (matches secrets ELEVEN_KEY_1/2/3)
ELEVEN_KEYS = [
    os.getenv("ELEVEN_KEY_1", ""),
    os.getenv("ELEVEN_KEY_2", ""),
    os.getenv("ELEVEN_KEY_3", ""),
]
ELEVEN_KEYS = [k for k in ELEVEN_KEYS if k.strip()]

# PixVerse API Keys Fallback List
# NOTE: your repo secrets are named PIXVERSE_KEY_1.._4 (see screenshot),
# the old code was reading PIXVERSE_API_KEY_1.._4 which do not exist -> always empty -> instant failure.
PIXVERSE_KEYS = [
    os.getenv("PIXVERSE_KEY_1", ""),
    os.getenv("PIXVERSE_KEY_2", ""),
    os.getenv("PIXVERSE_KEY_3", ""),
    os.getenv("PIXVERSE_KEY_4", ""),
]
PIXVERSE_KEYS = [k for k in PIXVERSE_KEYS if k.strip()]

KLING_API_KEY = os.getenv("KLING_API_KEY", "")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")
HEDRA_KEYS = [
    os.getenv("HEDRA_KEY_1", ""),
    os.getenv("HEDRA_KEY_2", ""),
    os.getenv("HEDRA_KEY_3", ""),
]
HEDRA_KEYS = [k for k in HEDRA_KEYS if k.strip()]

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


# ---------------------------------------------------------------------------
# PROVIDER 1: PixVerse
# ---------------------------------------------------------------------------
def generate_video_pixverse_single_key(api_key, prompt_text, idx):
    """Tries video generation with one specific PixVerse API Key
    (Official PixVerse Platform API: docs.platform.pixverse.ai)"""
    url = "https://app-api.pixverse.ai/openapi/v2/video/text/generate"
    headers = {
        "API-KEY": api_key,
        "Ai-trace-id": str(uuid.uuid4()),
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": prompt_text,
        "aspect_ratio": "9:16",
        "quality": "540p",
        "duration": 5,
        "model": "v3.5"
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

    if data.get("ErrCode") != 0:
        print(f"PixVerse API Error Response: {data}")
        return None

    video_id = data.get("Resp", {}).get("video_id")
    if not video_id:
        print(f"PixVerse response did not contain a video_id: {data}")
        return None

    print(f"PixVerse Video ID Created: {video_id}. Polling for render...")

    poll_url = f"https://app-api.pixverse.ai/openapi/v2/video/result/{video_id}"
    for attempt in range(40):
        time.sleep(10)
        poll_headers = {
            "API-KEY": api_key,
            "Ai-trace-id": str(uuid.uuid4())
        }
        try:
            status_res = requests.get(poll_url, headers=poll_headers, timeout=30)
            status_res.raise_for_status()
            status_data = status_res.json()
        except requests.exceptions.RequestException as e:
            print(f"PixVerse Poll Request Failed (attempt {attempt + 1}/40): {e}")
            continue
        except ValueError:
            print(f"PixVerse Poll returned non-JSON response (attempt {attempt + 1}/40)")
            continue

        resp_data = status_data.get("Resp", {})
        status = resp_data.get("status")

        if status == 1:  # Generation successful
            video_url = resp_data.get("url")
            if not video_url:
                print(f"PixVerse marked succeeded but no URL found: {status_data}")
                return None
            try:
                vid_bytes = requests.get(video_url, timeout=60).content
            except requests.exceptions.RequestException as e:
                print(f"Failed to download rendered PixVerse video: {e}")
                return None
            out_file = f"scene_{idx}_pixverse.mp4"
            with open(out_file, "wb") as f:
                f.write(vid_bytes)
            print(f"Scene {idx + 1} video rendered successfully via PixVerse!")
            return out_file
        elif status in (7, 8):  # 7 = content moderation failure, 8 = generation failed
            print(f"PixVerse Rendering Failed: {status_data}")
            return None
        # status == 5: still waiting for generation, keep polling

    print(f"PixVerse polling timed out after 40 attempts for video_id {video_id}")
    return None


def generate_video_pixverse(prompt_text, idx):
    """Loops through all available PixVerse Keys until one succeeds"""
    if not PIXVERSE_KEYS:
        print("PixVerse: no keys configured, skipping.")
        return None

    for key_idx, key in enumerate(PIXVERSE_KEYS):
        print(f"Attempting PixVerse Generation using Key #{key_idx + 1}...")
        try:
            out_file = generate_video_pixverse_single_key(key, prompt_text, idx)
        except Exception as e:
            print(f"PixVerse Key #{key_idx + 1} raised an unexpected error: {e}")
            out_file = None
        if out_file:
            return out_file
        print(f"Key #{key_idx + 1} failed or ran out of credits. Trying next key...")

    return None


# ---------------------------------------------------------------------------
# PROVIDER 2: Kling AI (official api-singapore.klingai.com endpoint)
# ---------------------------------------------------------------------------
def generate_video_kling(prompt_text, idx):
    """Text-to-video via Kling AI.
    NOTE: Kling's official API historically needs a JWT built from an
    Access Key + Secret Key. If your KLING_API_KEY secret is a single
    ready-made token (e.g. from a reseller/aggregator), this Bearer-token
    call will work as-is. If Kling keeps failing, check what format your
    key actually is - this provider is treated as optional/best-effort
    so it will never crash the run, it just gets skipped on failure.
    """
    if not KLING_API_KEY:
        print("Kling: no key configured, skipping.")
        return None

    base = "https://api-singapore.klingai.com/v1/videos/text2video"
    headers = {
        "Authorization": f"Bearer {KLING_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model_name": "kling-v1",
        "prompt": prompt_text,
        "negative_prompt": "",
        "duration": "5",
        "mode": "std",
        "aspect_ratio": "9:16"
    }

    try:
        res = requests.post(base, json=payload, headers=headers, timeout=30)
    except requests.exceptions.RequestException as e:
        print(f"Kling Request Failed (network/timeout): {e}")
        return None

    if res.status_code != 200:
        print(f"Kling API HTTP Error {res.status_code}: {res.text[:500]}")
        return None

    try:
        data = res.json()
    except ValueError:
        print(f"Kling API returned non-JSON response: {res.text[:500]}")
        return None

    task_id = (data.get("data") or {}).get("task_id")
    if not task_id:
        print(f"Kling response did not contain a task_id: {data}")
        return None

    print(f"Kling task created: {task_id}. Polling for render...")

    for attempt in range(40):
        time.sleep(10)
        try:
            poll_res = requests.get(
                f"{base}/{task_id}",
                headers={"Authorization": f"Bearer {KLING_API_KEY}"},
                timeout=30
            )
            poll_res.raise_for_status()
            poll_data = poll_res.json()
        except requests.exceptions.RequestException as e:
            print(f"Kling Poll Request Failed (attempt {attempt + 1}/40): {e}")
            continue
        except ValueError:
            print(f"Kling Poll returned non-JSON response (attempt {attempt + 1}/40)")
            continue

        task_data = poll_data.get("data") or {}
        status = task_data.get("task_status")

        if status == "succeed":
            videos = (task_data.get("task_result") or {}).get("videos") or []
            if not videos:
                print(f"Kling marked succeeded but no video found: {poll_data}")
                return None
            video_url = videos[0].get("url")
            if not video_url:
                print(f"Kling video entry missing url: {poll_data}")
                return None
            try:
                vid_bytes = requests.get(video_url, timeout=60).content
            except requests.exceptions.RequestException as e:
                print(f"Failed to download rendered Kling video: {e}")
                return None
            out_file = f"scene_{idx}_kling.mp4"
            with open(out_file, "wb") as f:
                f.write(vid_bytes)
            print(f"Scene {idx + 1} video rendered successfully via Kling!")
            return out_file
        elif status == "failed":
            print(f"Kling Rendering Failed: {poll_data}")
            return None
        # status == "submitted"/"processing": keep polling

    print(f"Kling polling timed out after 40 attempts for task_id {task_id}")
    return None


# ---------------------------------------------------------------------------
# PROVIDER 3: Replicate (cheap open model, works even on low free credit)
# ---------------------------------------------------------------------------
def generate_video_replicate(prompt_text, idx):
    """Text-to-video fallback using a fast/cheap open model hosted on Replicate."""
    if not REPLICATE_API_TOKEN:
        print("Replicate: no token configured, skipping.")
        return None

    url = "https://api.replicate.com/v1/models/wan-video/wan-2.5-t2v-fast/predictions"
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "input": {
            "prompt": prompt_text,
            "aspect_ratio": "9:16"
        }
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.exceptions.RequestException as e:
        print(f"Replicate Request Failed (network/timeout): {e}")
        return None

    if res.status_code not in (200, 201):
        print(f"Replicate API HTTP Error {res.status_code}: {res.text[:500]}")
        return None

    try:
        data = res.json()
    except ValueError:
        print(f"Replicate API returned non-JSON response: {res.text[:500]}")
        return None

    get_url = (data.get("urls") or {}).get("get")
    if not get_url:
        print(f"Replicate response missing poll URL: {data}")
        return None

    print("Replicate prediction created. Polling for render...")

    for attempt in range(40):
        time.sleep(10)
        try:
            poll_res = requests.get(get_url, headers=headers, timeout=30)
            poll_res.raise_for_status()
            poll_data = poll_res.json()
        except requests.exceptions.RequestException as e:
            print(f"Replicate Poll Request Failed (attempt {attempt + 1}/40): {e}")
            continue
        except ValueError:
            print(f"Replicate Poll returned non-JSON response (attempt {attempt + 1}/40)")
            continue

        status = poll_data.get("status")
        if status == "succeeded":
            output = poll_data.get("output")
            video_url = output[0] if isinstance(output, list) else output
            if not video_url:
                print(f"Replicate marked succeeded but no output found: {poll_data}")
                return None
            try:
                vid_bytes = requests.get(video_url, timeout=60).content
            except requests.exceptions.RequestException as e:
                print(f"Failed to download rendered Replicate video: {e}")
                return None
            out_file = f"scene_{idx}_replicate.mp4"
            with open(out_file, "wb") as f:
                f.write(vid_bytes)
            print(f"Scene {idx + 1} video rendered successfully via Replicate!")
            return out_file
        elif status in ("failed", "canceled"):
            print(f"Replicate Rendering Failed: {poll_data}")
            return None
        # status in ("starting", "processing"): keep polling

    print("Replicate polling timed out after 40 attempts.")
    return None


# ---------------------------------------------------------------------------
# PROVIDER 4: Hugging Face free "Wan2.1" Space (genuinely free, real motion -
# not a zoom/pan on a photo, an actual generated video clip).
# Uses HF's shared free ZeroGPU quota, so it is slower and lower-resolution
# than PixVerse/Kling, and can be queued/rate-limited since it's shared by
# everyone. HF_TOKEN (already in your secrets) raises your daily quota.
# ---------------------------------------------------------------------------
def generate_video_hf_wan(prompt_text, idx):
    """Real (non-zoom) free video generation via the public Wan-AI/Wan2.1 Space."""
    try:
        from gradio_client import Client
    except ImportError:
        print("HF Wan2.1: gradio_client not installed, skipping (add it to requirements.txt).")
        return None

    if not HF_TOKEN:
        print("HF Wan2.1: no HF_TOKEN set, trying anonymously (very low quota)...")

    # Different gradio_client versions have renamed this parameter
    # (older: hf_token, newer: token). Try each so we don't crash with
    # "unexpected keyword argument" just because of a version mismatch.
    client = None
    client_errors = []
    if HF_TOKEN:
        for kwarg_name in ("hf_token", "token"):
            try:
                client = Client("Wan-AI/Wan2.1", **{kwarg_name: HF_TOKEN})
                break
            except TypeError as e:
                client_errors.append(f"{kwarg_name}: {e}")
    if client is None:
        try:
            client = Client("Wan-AI/Wan2.1")
        except Exception as e:
            print(f"HF Wan2.1 Space connection failed: {e}"
                  + (f" (auth attempts also failed: {client_errors})" if client_errors else ""))
            return None

    try:
        # NOTE: the exact api_name/parameter names of this Space can change
        # over time - if this errors, run client.view_api() locally once to
        # see the current schema and I'll adjust the call for you.
        result = client.predict(
            prompt_text,
            "",          # negative_prompt
            480,         # resolution/size (Space-dependent)
            5,           # duration (seconds) - Space-dependent
            api_name="/generate_video"
        )
    except Exception as e:
        print(f"HF Wan2.1 Space call failed: {e}")
        return None

    # result is usually a filepath (str) or a dict with a 'video' path
    video_path = result if isinstance(result, str) else (result or {}).get("video")
    if not video_path or not os.path.exists(video_path):
        print(f"HF Wan2.1: unexpected response, no video file found: {result}")
        return None

    out_file = f"scene_{idx}_hfwan.mp4"
    try:
        with open(video_path, "rb") as src, open(out_file, "wb") as dst:
            dst.write(src.read())
        print(f"Scene {idx + 1}: video generated via free HF Wan2.1 Space.")
        return out_file
    except OSError as e:
        print(f"HF Wan2.1: failed to copy result file: {e}")
        return None


def generate_video_any_provider(prompt_text, idx):
    """Tries every provider in order and never raises - always returns
    either a video file path or None."""
    providers = [
        ("PixVerse", generate_video_pixverse),
        ("Kling", generate_video_kling),
        ("Replicate", generate_video_replicate),
        ("HF Wan2.1 (free)", generate_video_hf_wan),
    ]
    for name, func in providers:
        print(f"--- Trying provider: {name} ---")
        try:
            result = func(prompt_text, idx)
        except Exception as e:
            print(f"{name} raised an unexpected error, skipping: {e}")
            result = None
        if result:
            return result
        print(f"{name} did not produce a video, moving to next provider...")

    print("All video providers failed - no fake placeholder will be used.")
    return None


def assemble_scene(video_file, script_text, idx):
    """Syncs Audio with the generated video"""
    audio_file = f"audio_{idx}.mp3"

    eleven_success = False
    for key_idx, key in enumerate(ELEVEN_KEYS):
        try:
            url = "https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB"
            headers = {"xi-api-key": key, "Content-Type": "application/json"}
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
                break
            else:
                print(f"ElevenLabs Key #{key_idx + 1} Error {res.status_code}: {res.text[:300]}")
        except requests.exceptions.RequestException as e:
            print(f"ElevenLabs Key #{key_idx + 1} Error: {e}")

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
    print("=== Fully Automated Multi-Provider AI Short Bot Started ===")
    print(f"PixVerse keys available: {len(PIXVERSE_KEYS)}")
    print(f"Kling key available: {bool(KLING_API_KEY)}")
    print(f"Replicate token available: {bool(REPLICATE_API_TOKEN)}")
    print(f"HF token available (for free Wan2.1 fallback): {bool(HF_TOKEN)}")
    print(f"ElevenLabs keys available: {len(ELEVEN_KEYS)}")

    story = generate_story_script()
    scenes = story["scenes"]
    final_clips = []

    for idx, scene in enumerate(scenes):
        print(f"\n--- Processing Scene {idx + 1} ---")
        try:
            raw_video = generate_video_any_provider(scene["prompt"], idx)
            if raw_video:
                clip = assemble_scene(raw_video, scene["script"], idx)
                final_clips.append(clip)
            else:
                print(f"Scene {idx + 1} skipped: no video was generated by any provider.")
        except Exception as e:
            print(f"Scene {idx + 1} failed with an unexpected error: {e}")

    if final_clips:
        try:
            final_video = merge_clips(final_clips)
        except Exception as e:
            print(f"\nFAILED: Could not merge clips into final video: {e}")
            sys.exit(1)
        print(f"\nSUCCESS: Fully Automated Short Ready: {final_video}")
    else:
        print("\nFAILED: Video generation unsuccessful. No clips were produced "
              "(check API keys/credits and API responses above).")
        sys.exit(1)
