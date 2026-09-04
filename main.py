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

# --- YouTube auto-upload (free, YouTube Data API v3 - see
# get_youtube_refresh_token.py for one-time setup) --------------------
YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN", "")
# Defaults to "private" on purpose: fallback scenes (Pollinations zoom)
# can look noticeably weaker than a real AI-video scene, so uploads stay
# private until you've checked a few and are happy with the quality.
# Once happy, set this GitHub secret/variable to "public".
YT_PRIVACY_STATUS = os.getenv("YT_PRIVACY_STATUS", "private")

# How many scenes per short. More scenes = longer final video.
# With ~6-8s of Hindi dialogue per scene, 5 scenes lands close to 30-40s.
NUM_SCENES = int(os.getenv("NUM_SCENES", "5"))

# ElevenLabs keys fallback list (matches secrets ELEVEN_KEY_1/2/3)
ELEVEN_KEYS = [
    os.getenv("ELEVEN_KEY_1", ""),
    os.getenv("ELEVEN_KEY_2", ""),
    os.getenv("ELEVEN_KEY_3", ""),
]
ELEVEN_KEYS = [k for k in ELEVEN_KEYS if k.strip()]

# PixVerse API Keys Fallback List
# NOTE: PixVerse is NOT actually free - it needs purchased credits.
# These are only tried opportunistically in case you top up credits later.
PIXVERSE_KEYS = [
    os.getenv("PIXVERSE_KEY_1", ""),
    os.getenv("PIXVERSE_KEY_2", ""),
    os.getenv("PIXVERSE_KEY_3", ""),
    os.getenv("PIXVERSE_KEY_4", ""),
]
PIXVERSE_KEYS = [k for k in PIXVERSE_KEYS if k.strip()]

# Kling official API also needs a paid/approved account - optional/best-effort.
KLING_API_KEY = os.getenv("KLING_API_KEY", "")

# Replicate gives a very small free trial credit, then needs a payment
# method for rate limits - optional/best-effort.
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")

# --- Hugging Face free Spaces (the only provider here that is genuinely
# free forever, no card required) -------------------------------------
# Each free HF account gets a small daily ZeroGPU quota (a couple of
# minutes). To stretch that, we rotate across every HF token you give us
# (HF_TOKEN_1..HF_TOKEN_4, or the older single HF_TOKEN secret), and across
# every Space listed in HF_VIDEO_SPACES (comma separated, so you can add/
# swap working Spaces without touching code).
HF_TOKENS = []
if os.getenv("HF_TOKEN", "").strip():
    HF_TOKENS.append(os.getenv("HF_TOKEN").strip())
for i in range(1, 5):
    tok = os.getenv(f"HF_TOKEN_{i}", "").strip()
    if tok:
        HF_TOKENS.append(tok)
HF_TOKENS = list(dict.fromkeys(HF_TOKENS))  # dedupe, keep order

HF_VIDEO_SPACES = [
    s.strip() for s in os.getenv("HF_VIDEO_SPACES", "Wan-AI/Wan2.1").split(",")
    if s.strip()
]

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


# ---------------------------------------------------------------------------
# Fallback story pool (used if Gemini is unavailable/fails). Cycled to fill
# NUM_SCENES so the default story still hits the ~30-40s target.
# ---------------------------------------------------------------------------
DEFAULT_SCENE_POOL = [
    {
        "prompt": "3D Pixar style animated cute potato character talking dynamically in colorful market",
        "script": "ओ यारों, आज मैं नया कारोबार शुरू करने निकला हूँ, देखते हैं क्या होता है!"
    },
    {
        "prompt": "3D Pixar style animated angry eggplant character shouting furiously",
        "script": "अरे बैंगन भाई, तुम मुझसे इतना जलते क्यों हो, थोड़ा तो प्यार से बात करो!"
    },
    {
        "prompt": "3D Pixar style animated confused onion character scratching head",
        "script": "यार प्याज भाई, तेरी बात सुनकर तो मेरी आँखों में आँसू आ गए!"
    },
    {
        "prompt": "3D Pixar style animated excited tomato character jumping happily",
        "script": "चलो सब मिलकर सब्ज़ी मंडी में धमाल मचाते हैं, आज मज़ा आएगा!"
    },
    {
        "prompt": "3D Pixar style animated group of vegetable characters laughing together",
        "script": "और इस तरह ये अजीबो-गरीब सब्ज़ियां रोज़ नया तमाशा खड़ा कर देती थीं!"
    },
]


def generate_story_script():
    """Generates an NUM_SCENES-scene story script via Gemini."""
    print("Generating Story Script via Gemini...")

    default_scenes = list(itertools.islice(itertools.cycle(DEFAULT_SCENE_POOL), NUM_SCENES))
    default_data = {"scenes": default_scenes}

    if not gemini_client:
        print("Gemini client not available, falling back to default script.")
        return default_data

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest"]

    format_lines = []
    for i in range(1, NUM_SCENES + 1):
        format_lines.append(f"SCENE {i} PROMPT: [Video prompt]")
        format_lines.append(f"SCENE {i} SCRIPT: [Hindi dialogue line]")
    format_block = "\n".join(format_lines)

    prompt_text = (
        f"Create a funny {NUM_SCENES}-scene animated Hindi short story starring 3D cartoon veggie "
        "characters, continuing one storyline across all scenes. Each scene must have a visual video "
        "prompt in English describing action/motion (max 12 words) and 1 pure Hindi dialogue line of "
        "about 15-20 words (roughly 6-8 seconds when spoken aloud), so the whole short runs about "
        f"30-40 seconds across all {NUM_SCENES} scenes.\n\n"
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
                    clean_prompt = video_prompts[i].strip() + ", 3D animated Pixar style, 9:16 vertical video"
                    if clean_script and clean_prompt:
                        scenes.append({"prompt": clean_prompt, "script": clean_script})
                if len(scenes) == NUM_SCENES:
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
# PROVIDER 1: PixVerse (NOT free - needs purchased credits; kept as a
# best-effort bonus provider in case you top up credits later)
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
# NOT free either without an approved/paid account - optional/best-effort.
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
# PROVIDER 3: Replicate (small free trial credit only, then needs a
# payment method - optional/best-effort)
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
# PROVIDER 4: Hugging Face free Spaces (genuinely free, no card, no
# subscription - this is the real "free" tier). Uses HF's shared ZeroGPU
# quota, so it's slow/low-res and each account only gets a couple of
# minutes/day - that's why we rotate across every token in HF_TOKENS and
# every Space in HF_VIDEO_SPACES.
#
# IMPORTANT: gradio_client's Client() constructor has changed its token
# keyword name across versions (hf_token vs token), which is exactly what
# crashed the old code ("unexpected keyword argument 'hf_token'"). We
# detect the right keyword at runtime instead of hard-coding it, so this
# keeps working regardless of which gradio_client version CI installs.
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
        # else: this version doesn't take a token kwarg at all - connect anonymously
    return Client(space_id, **kwargs)


def generate_video_hf_spaces(prompt_text, idx):
    """Real (non-zoom) free video generation via public Hugging Face Spaces."""
    try:
        from gradio_client import Client  # noqa: F401 (import check only)
    except ImportError:
        print("HF Spaces: gradio_client not installed, skipping (add it to requirements.txt).")
        return None

    tokens_to_try = HF_TOKENS if HF_TOKENS else [None]

    for space_id in HF_VIDEO_SPACES:
        for token_idx, token in enumerate(tokens_to_try):
            label = f"{space_id} (HF token #{token_idx + 1})" if token else f"{space_id} (anonymous, low quota)"
            print(f"HF Spaces: trying {label}...")
            try:
                client = _make_hf_client(space_id, token)
                # NOTE: the exact api_name/parameter names/order of a Space's
                # API can change over time. If this errors for your chosen
                # Space, run client.view_api() locally once to see the
                # current schema and adjust the call below to match.
                result = client.predict(
                    prompt_text,
                    "",          # negative_prompt
                    480,         # resolution/size (Space-dependent)
                    5,           # duration (seconds) - Space-dependent
                    api_name="/generate_video"
                )
            except Exception as e:
                print(f"HF Spaces {label} failed: {e}")
                continue

            # result is usually a filepath (str), a dict with a 'video' path,
            # or a list/tuple wrapping either of those.
            video_path = result
            if isinstance(video_path, (list, tuple)) and video_path:
                video_path = video_path[0]
            if isinstance(video_path, dict):
                video_path = video_path.get("video") or video_path.get("path")

            if not video_path or not os.path.exists(video_path):
                print(f"HF Spaces {label}: unexpected response, no video file found: {result}")
                continue

            out_file = f"scene_{idx}_hf.mp4"
            try:
                with open(video_path, "rb") as src, open(out_file, "wb") as dst:
                    dst.write(src.read())
                print(f"Scene {idx + 1}: video generated via free HF Space {space_id}.")
                return out_file
            except OSError as e:
                print(f"HF Spaces {label}: failed to copy result file: {e}")
                continue

    return None


# ---------------------------------------------------------------------------
# PROVIDER 5 (guaranteed fallback): free Pollinations.ai AI image (no key,
# no signup, no rate-limit wall) animated into a moving clip with ffmpeg's
# zoompan filter (Ken Burns style slow zoom/pan). This is what stops the
# whole pipeline from ever fully failing when every video-AI provider
# above is out of credits, rate-limited, or down - it still ships a real
# AI-generated visual for the scene instead of nothing.
# ---------------------------------------------------------------------------
def generate_video_pollinations_zoom(prompt_text, idx):
    img_prompt = requests.utils.quote(f"{prompt_text}, vertical, high detail")
    img_url = f"https://image.pollinations.ai/prompt/{img_prompt}?width=1080&height=1920&nologo=true"
    img_file = f"scene_{idx}_pollinations.jpg"

    try:
        res = requests.get(img_url, timeout=60)
        res.raise_for_status()
        with open(img_file, "wb") as f:
            f.write(res.content)
    except requests.exceptions.RequestException as e:
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

    print(f"Scene {idx + 1}: fallback video built from a free Pollinations AI image + Ken Burns zoom.")
    return out_file


def generate_video_any_provider(prompt_text, idx):
    """Tries every provider in order and never raises - always returns
    either a video file path or None. The last provider is a guaranteed
    free fallback, so in practice this should basically never return None."""
    providers = [
        ("PixVerse", generate_video_pixverse),
        ("Kling", generate_video_kling),
        ("Replicate", generate_video_replicate),
        ("HF Spaces (free)", generate_video_hf_spaces),
        ("Pollinations free image + zoom (guaranteed fallback)", generate_video_pollinations_zoom),
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

    print("All video providers failed, including the guaranteed fallback (check network/ffmpeg).")
    return None


def get_media_duration(path):
    """Returns the duration (seconds) of an audio/video file via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


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

    try:
        audio_duration = get_media_duration(audio_file)
    except Exception as e:
        print(f"Could not read audio duration ({e}), defaulting to 6s.")
        audio_duration = 6.0

    # NOTE: "-stream_loop -1" loops the (usually short, 2-8s) generated
    # video so the dialogue is never cut short - the clip always runs the
    # full length of the audio, however long that scene's line is.
    output_clip = f"clip_{idx}.mp4"
    ffmpeg_cmd = [
        "ffmpeg",
        "-stream_loop", "-1",
        "-i", video_file,
        "-i", audio_file,
        "-filter_complex", "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v]",
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-t", f"{audio_duration:.2f}",
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


# ---------------------------------------------------------------------------
# YouTube auto-upload (free - YouTube Data API v3). Skips quietly if the
# YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN secrets aren't set, so
# the rest of the pipeline (video generation + artifact upload) keeps
# working exactly as before even if you never set this up.
# ---------------------------------------------------------------------------
def upload_to_youtube(video_path, title, description):
    if not (YT_CLIENT_ID and YT_CLIENT_SECRET and YT_REFRESH_TOKEN):
        print("YouTube upload: YT_CLIENT_ID/YT_CLIENT_SECRET/YT_REFRESH_TOKEN not set, "
              "skipping upload (video is still saved as a workflow artifact). "
              "See get_youtube_refresh_token.py for free one-time setup.")
        return None

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        print("YouTube upload: google-api-python-client/google-auth not installed, skipping.")
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
                "categoryId": "23",  # Comedy
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
        print(f"Uploaded to YouTube ({YT_PRIVACY_STATUS}): https://youtube.com/shorts/{video_id}")
        return video_id
    except Exception as e:
        print(f"YouTube upload failed: {e}")
        return None


if __name__ == "__main__":
    print("=== Fully Automated Multi-Provider AI Short Bot Started ===")
    print(f"Target scenes: {NUM_SCENES}")
    print(f"PixVerse keys available (paid): {len(PIXVERSE_KEYS)}")
    print(f"Kling key available (paid): {bool(KLING_API_KEY)}")
    print(f"Replicate token available (paid/trial): {bool(REPLICATE_API_TOKEN)}")
    print(f"HF tokens available (free): {len(HF_TOKENS)}")
    print(f"HF video Spaces to try (free): {HF_VIDEO_SPACES}")
    print(f"ElevenLabs keys available: {len(ELEVEN_KEYS)}")

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
            else:
                print(f"Scene {idx + 1} skipped: no video was generated by any provider.")
        except Exception as e:
            print(f"Scene {idx + 1} failed with an unexpected error: {e}")

    if final_clips:
        try:
            final_video = merge_clips(final_clips)
            total_duration = get_media_duration(final_video)
        except Exception as e:
            print(f"\nFAILED: Could not merge clips into final video: {e}")
            sys.exit(1)
        print(f"\nSUCCESS: Fully Automated Short Ready: {final_video} (~{total_duration:.1f}s)")

        yt_title = "मज़ेदार सब्ज़ी कहानी 🥔🍆 #Shorts"
        yt_description = "\n".join(s["script"] for s in scenes) + "\n\n#Shorts #Comedy #Hindi #AIAnimation"
        upload_to_youtube(final_video, yt_title, yt_description)
    else:
        print("\nFAILED: Video generation unsuccessful. No clips were produced "
              "(check API keys/credits and API responses above).")
        sys.exit(1)
