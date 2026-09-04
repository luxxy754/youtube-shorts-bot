import os
import re
import sys
import time
import uuid
import inspect
import itertools
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

# --- YouTube auto-upload (free, YouTube Data API v3) --------------------
YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN", "")
YT_PRIVACY_STATUS = os.getenv("YT_PRIVACY_STATUS", "private")

NUM_SCENES = int(os.getenv("NUM_SCENES", "5"))

# ElevenLabs keys fallback list
ELEVEN_KEYS = [
    os.getenv("ELEVEN_KEY_1", ""),
    os.getenv("ELEVEN_KEY_2", ""),
    os.getenv("ELEVEN_KEY_3", ""),
]
ELEVEN_KEYS = [k for k in ELEVEN_KEYS if k.strip()]

# Hugging Face free Spaces for base video generation
HF_TOKENS = []
if os.getenv("HF_TOKEN", "").strip():
    HF_TOKENS.append(os.getenv("HF_TOKEN").strip())
for i in range(1, 5):
    tok = os.getenv(f"HF_TOKEN_{i}", "").strip()
    if tok:
        HF_TOKENS.append(tok)
HF_TOKENS = list(dict.fromkeys(HF_TOKENS))

HF_VIDEO_SPACES = [
    s.strip() for s in os.getenv("HF_VIDEO_SPACES", "Wan-AI/Wan2.1").split(",")
    if s.strip()
]

gemini_client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Warning: {e}")


# ---------------------------------------------------------------------------
# Fallbarck story pool with hyper-realistic cinematic style & backgrounds
# ---------------------------------------------------------------------------
DEFAULT_SCENE_POOL = [
    {
        "prompt": "Hyper-realistic 3D animated cute cat character talking dynamically, highly detailed fur, cinematic studio lighting, bokeh background of a cozy modern room with warm LED lights, 8k resolution, vertical 9:16",
        "script": "ओ यारों, आज मैं नया कारोबार शुरू करने निकला हूँ, देखते हैं क्या होता है!"
    },
    {
        "prompt": "Hyper-realistic 3D animated fresh vegetable character shouting furiously, rich textures, dramatic cinematic rim lighting, blurred organic farm market background, 8k resolution, vertical 9:16",
        "script": "अरे भाई, तुम मुझसे इतना जलते क्यों हो, थोड़ा तो प्यार से बात करो!"
    },
    {
        "prompt": "Hyper-realistic 3D animated confused character scratching head, highly detailed features, cinematic soft lighting, aesthetic modern kitchen background with depth of field, 8k resolution, vertical 9:16",
        "script": "यार तेरी बात सुनकर तो मेरी आँखें खुली की खुली रह गईं!"
    },
    {
        "prompt": "Hyper-realistic 3D animated excited character jumping happily, vibrant realistic colors, cinematic outdoor park background with sunlight flare, 8k resolution, vertical 9:16",
        "script": "चलो सब मिलकर आज इस माहौल में धमाल मचाते हैं, बड़ा मज़ा आएगा!"
    },
    {
        "prompt": "Hyper-realistic 3D animated group of characters laughing together, intricate details, cinematic indoor lounge background, warm ambient lighting, 8k resolution, vertical 9:16",
        "script": "और इस तरह रोज़ एक नया तमाशा खड़ा हो जाता है!"
    },
]


def generate_story_script():
    """Generates an NUM_SCENES-scene realistic story script via Gemini."""
    print("Generating Realistic Story Script via Gemini...")

    default_scenes = list(itertools.islice(itertools.cycle(DEFAULT_SCENE_POOL), NUM_SCENES))
    default_data = {"scenes": default_scenes}

    if not gemini_client:
        return default_data

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest"]

    format_lines = []
    for i in range(1, NUM_SCENES + 1):
        format_lines.append(f"SCENE {i} PROMPT: [Video prompt]")
        format_lines.append(f"SCENE {i} SCRIPT: [Hindi dialogue line]")
    format_block = "\n".join(format_lines)

    prompt_text = (
        f"Create a funny {NUM_SCENES}-scene animated Hindi short story starring hyper-realistic 3D characters "
        "(like cats, cute animals or realistic styled characters), continuing one storyline. Each scene must have an ultra-detailed "
        "visual video prompt in English describing action, rich textures, cinematic lighting and a realistic background (max 15 words) "
        "and 1 pure Hindi dialogue line (roughly 6-8 seconds when spoken), so the whole short runs about 30-40 seconds.\n\n"
        "STRICT FORMAT (no extra text before/after):\n" + format_block
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

            if len(video_prompts) >= NUM_SCENES and len(scripts) >= NUM_SCENES:
                for i in range(NUM_SCENES):
                    clean_script = re.sub(r'\(.*?\)', '', scripts[i]).replace('*', '').replace('"', '').strip()
                    clean_prompt = video_prompts[i].strip() + ", hyper-realistic 3D animation, ultra-detailed textures, cinematic lighting, 8k, 9:16 vertical video"
                    if clean_script and clean_prompt:
                        scenes.append({"prompt": clean_prompt, "script": clean_script})
                if len(scenes) == NUM_SCENES:
                    return {"scenes": scenes}
        except Exception as e:
            print(f"Gemini Story Error ({model_name}): {e}")

    return default_data


# ---------------------------------------------------------------------------
# PROVIDER: Hugging Face Spaces for base realistic video generation
# ---------------------------------------------------------------------------
def _make_hf_client(space_id, token):
    from gradio_client import Client
    kwargs = {}
    if token:
        try:
            sig_params = inspect.signature(Client.__init__).parameters
        except (TypeError, ValueError):
            sig_params = {}
        if "hf_token" in sig_params:
            kwargs["hf_token"] = token
        elif "token" in sig_params:
            kwargs["token"] = token
    return Client(space_id, **kwargs)


def generate_video_hf_spaces(prompt_text, idx):
    try:
        from gradio_client import Client  # noqa: F401
    except ImportError:
        return None

    tokens_to_try = HF_TOKENS if HF_TOKENS else [None]

    for space_id in HF_VIDEO_SPACES:
        for token_idx, token in enumerate(tokens_to_try):
            label = f"{space_id} (HF token #{token_idx + 1})" if token else f"{space_id} (anonymous)"
            print(f"HF Spaces: trying {label}...")
            try:
                client = _make_hf_client(space_id, token)
                result = client.predict(
                    prompt_text,
                    "",          # negative_prompt
                    480,         # resolution
                    5,           # duration
                    api_name="/generate_video"
                )
            except Exception as e:
                print(f"HF Spaces {label} failed: {e}")
                continue

            video_path = result
            if isinstance(video_path, (list, tuple)) and video_path:
                video_path = video_path[0]
            if isinstance(video_path, dict):
                video_path = video_path.get("video") or video_path.get("path")

            if not video_path or not os.path.exists(video_path):
                continue

            out_file = f"scene_{idx}_hf.mp4"
            try:
                with open(video_path, "rb") as src, open(out_file, "wb") as dst:
                    dst.write(src.read())
                return out_file
            except OSError:
                continue
    return None


# ---------------------------------------------------------------------------
# GUARANTEED FALLBACK: Pollinations realistic image + Ken Burns Zoom
# ---------------------------------------------------------------------------
def generate_video_pollinations_zoom(prompt_text, idx):
    img_prompt = requests.utils.quote(f"{prompt_text}, hyper-realistic, photorealistic background, 8k, vertical")
    img_url = f"https://image.pollinations.ai/prompt/{img_prompt}?width=1080&height=1920&nologo=true"
    img_file = f"scene_{idx}_pollinations.jpg"

    try:
        res = requests.get(img_url, timeout=60)
        res.raise_for_status()
        with open(img_file, "wb") as f:
            f.write(res.content)
    except Exception as e:
        print(f"Pollinations image fetch failed: {e}")
        return None

    out_file = f"scene_{idx}_pollinations.mp4"
    zoom_cmd = [
        "ffmpeg",
        "-loop", "1",
        "-i", img_file,
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "zoompan=z='min(zoom+0.0015,1.4)':d=200:s=1080x1920:fps=25",
        "-t", "8",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-y",
        out_file
    ]
    try:
        subprocess.run(zoom_cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg zoompan failed: {e.stderr}")
        return None

    return out_file


def generate_video_any_provider(prompt_text, idx):
    providers = [
        ("HF Spaces (free)", generate_video_hf_spaces),
        ("Pollinations free realistic image + zoom (guaranteed fallback)", generate_video_pollinations_zoom),
    ]
    for name, func in providers:
        print(f"--- Trying provider: {name} ---")
        try:
            result = func(prompt_text, idx)
        except Exception as e:
            print(f"{name} error: {e}")
            result = None
        if result:
            return result
    return None


def get_media_duration(path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


# ---------------------------------------------------------------------------
# WAV2LIP INTEGRATION (Replaces Hedra completely, 100% free, no API key needed)
# ---------------------------------------------------------------------------
def setup_wav2lip():
    if not os.path.exists("Wav2Lip"):
        print("Cloning Wav2Lip repository...")
        subprocess.run(["git", "clone", "https://github.com/Rudrabha/Wav2Lip.git"], check=True)
        # Download pre-trained weights if not present
        os.makedirs("Wav2Lip/checkpoints", exist_ok=True)
        # Using standard lightweight checkpoints download links or mirror
        print("Downloading Wav2Lip model weights...")
        weights_url = "https://huggingface.co/spaces/nateraw/wav2lip/resolve/main/checkpoints/wav2lip.pth"
        r = requests.get(weights_url)
        with open("Wav2Lip/checkpoints/wav2lip.pth", "wb") as f:
            f.write(r.content)
            
        s3fd_url = "https://huggingface.co/spaces/nateraw/wav2lip/resolve/main/checkpoints/s3fd.pth"
        os.makedirs("Wav2Lip/face_detection/detection/s3fd", exist_ok=True)
        r2 = requests.get(s3fd_url)
        with open("Wav2Lip/face_detection/detection/s3fd/s3fd.pth", "wb") as f:
            f.write(r2.content)


def apply_wav2lip_lipsync(video_file, audio_file, output_clip, idx):
    """Applies Wav2Lip local open-source lipsync without any paid API."""
    setup_wav2lip()
    
    inference_script = "Wav2Lip/inference.py"
    checkpoint_path = "Wav2Lip/checkpoints/wav2lip.pth"
    
    cmd = [
        "python", inference_script,
        "--checkpoint_path", checkpoint_path,
        "--face", video_file,
        "--audio", audio_file,
        "--outfile", output_clip,
        "--pads", "0", "10", "0", "0"
    ]
    
    try:
        print(f"Running Wav2Lip lipsync for scene {idx + 1}...")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        if os.path.exists(output_clip):
            return output_clip
    except subprocess.CalledProcessError as e:
        print(f"Wav2Lip error: {e.stderr}")
    
    # Fallback: if lipsync fails for any reason, use standard video+audio merge
    print("Wav2Lip skipped/failed, falling back to standard video assembly...")
    audio_duration = get_media_duration(audio_file)
    fallback_cmd = [
        "ffmpeg", "-stream_loop", "-1", "-i", video_file, "-i", audio_file,
        "-filter_complex", "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v]",
        "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-c:a", "aac",
        "-t", f"{audio_duration:.2f}", "-y", output_clip
    ]
    subprocess.run(fallback_cmd, check=True, capture_output=True, text=True)
    return output_clip


def assemble_scene(video_file, script_text, idx):
    """Syncs Audio with generated video and applies Wav2Lip lipsync"""
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
        except Exception:
            pass

    if not eleven_success:
        try:
            tts = gTTS(text=script_text, lang="hi", slow=False)
            tts.save(audio_file)
        except Exception as e:
            print(f"gTTS fallback failed: {e}")
            raise

    output_clip = f"clip_{idx}.mp4"
    # Apply Wav2Lip lipsync using the generated video and audio
    return apply_wav2lip_lipsync(video_file, audio_file, output_clip, idx)


def merge_clips(clip_files, final_output="final_short.mp4"):
    with open("files.txt", "w") as f:
        for clip in clip_files:
            f.write(f"file '{clip}'\n")

    concat_cmd = [
        "ffmpeg", "-f", "concat", "-safe", "0",
        "-i", "files.txt", "-c", "copy", "-y", final_output
    ]
    subprocess.run(concat_cmd, check=True, capture_output=True, text=True)
    return final_output


def upload_to_youtube(video_path, title, description):
    if not (YT_CLIENT_ID and YT_CLIENT_SECRET and YT_REFRESH_TOKEN):
        return None

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        return None

    creds = Credentials(
        token=None,
        refresh_token=YT_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )

    try:
        youtube = build("youtube", "v3", credentials=creds)
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": ["shorts", "comedy", "hindi", "AI animation"],
                "categoryId": "23",
            },
            "status": {
                "privacyStatus": YT_PRIVACY_STATUS,
                "selfDeclaredMadeForKids": False,
            },
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
        video_id = response.get("id")
        print(f"Uploaded to YouTube: https://youtube.com/shorts/{video_id}")
        return video_id
    except Exception as e:
        print(f"YouTube upload failed: {e}")
        return None


if __name__ == "__main__":
    print("=== Fully Automated AI Short Bot with Wav2Lip Started ===")
    story = generate_story_script()
    scenes = story["scenes"]
    final_clips = []

    for idx, scene in enumerate(scenes):
        print(f"\n--- Processing Scene {idx + 1}/{len(scenes)} ---")
        try:
            raw_video = generate_video_any_provider(scene["prompt"], idx)
            if raw_video:
                clip = assemble_scene(raw_video, scene["script"], idx)
                final_clips.append(clip)
        except Exception as e:
            print(f"Scene {idx + 1} failed: {e}")

    if final_clips:
        try:
            final_video = merge_clips(final_clips)
            total_duration = get_media_duration(final_video)
        except Exception as e:
            print(f"\nFAILED: {e}")
            sys.exit(1)
        print(f"\nSUCCESS: Short Ready: {final_video} (~{total_duration:.1f}s)")

        yt_title = "मज़ेदार AI कहानी #Shorts"
        yt_description = "\n".join(s["script"] for s in scenes) + "\n\n#Shorts #Comedy #Hindi #AIAnimation"
        upload_to_youtube(final_video, yt_title, yt_description)
    else:
        print("\nFAILED: No clips produced.")
        sys.exit(1)
