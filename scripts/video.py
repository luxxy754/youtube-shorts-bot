"""Video generation for the YouTube Shorts bot.

Priority:
1. fal.ai MiniMax H3 Max (free 5/day per signed-in account)
2. Agnes AI (free fallback)
3. HuggingFace Spaces fallback
4. Image-motion fallback (last resort)

fal.ai: Get key at https://fal.ai → sign in → API Keys
"""

import os
import re
import shutil
import subprocess
import time
from urllib.parse import quote

import requests

CLIP_SECONDS = int(os.getenv("CLIP_SECONDS", "4"))

FREE_MODE = os.getenv("FREE_MODE", "1").lower() in {"1", "true", "yes"}

IMAGES_PER_SCENE = max(1, int(os.getenv("IMAGES_PER_SCENE", "4")))

AGNES_MODEL = os.getenv("AGNES_MODEL", "agnes-video-2.5-flash")
AGNES_BASE = "https://apihub.agnes-ai.com/v1"

HF_SPACES = [
    "Wan-AI/Wan2.1-T2V-14B",
    "Lightricks/LTX-Video",
]

_HF_DEAD = set()


# ---------------------------------------------------------
# fal.ai MiniMax H3 Max (free 5/day per key)
# ---------------------------------------------------------

def fal_video(prompt, path):
    """fal.ai MiniMax H3 Max — free 5 generations/day per signed-in account."""
    keys = [os.getenv(f"FAL_KEY_{i}", "").strip() for i in range(1, 4)]
    keys = [k for k in keys if k]

    if not keys:
        print("  FAL_KEY_1/FAL_KEY_2 not set")
        return False

    try:
        import fal_client
    except ImportError:
        print("  fal_client not installed. Add 'fal-client' to requirements.txt")
        return False

    for idx, key in enumerate(keys):
        try:
            os.environ["FAL_KEY"] = key
            print(f"  fal.ai (key {idx + 1}) generating...")

            result = fal_client.subscribe(
                "minimax/h3-max/text-to-video",
                arguments={
                    "prompt": prompt,
                    "resolution": "768P",
                    "aspect_ratio": "9:16",
                    "duration": CLIP_SECONDS,
                },
                with_logs=False,
            )

            video_url = result["video"]["url"]
            data = requests.get(video_url, timeout=180)
            with open(path, "wb") as f:
                f.write(data.content)

            print(f"  fal.ai success (key {idx + 1})")
            return True

        except Exception as exc:
            msg = str(exc).lower()
            if any(w in msg for w in ("quota", "rate", "429", "exceeded", "limit")):
                print(f"  fal.ai key {idx + 1} exhausted, trying next...")
                continue
            print(f"  fal.ai error: {str(exc)[:200]}")
            continue

    return False


# ---------------------------------------------------------
# Agnes AI (free fallback)
# ---------------------------------------------------------

def agnes_video(prompt, path):
    """Agnes AI free text-to-video."""
    key = os.getenv("AGNES_API_KEY", "").strip()
    if not key:
        print("  AGNES_API_KEY not set")
        return False

    try:
        print(f"  Creating Agnes task (model={AGNES_MODEL})...")

        create = requests.post(
            f"{AGNES_BASE}/videos",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": AGNES_MODEL,
                "prompt": prompt,
                "mode": "text",
                "seconds": str(CLIP_SECONDS),
                "size": "720P",
                "aspect_ratio": "9:16",
            },
            timeout=60,
        )

        if create.status_code != 200:
            print(f"  Agnes create failed HTTP {create.status_code}: {create.text[:200]}")
            return False

        data = create.json()
        video_id = data.get("video_id") or data.get("id") or data.get("task_id")
        if not video_id:
            print(f"  Agnes: no video_id in response: {data}")
            return False

        print(f"  Agnes task created: {video_id}")

        max_wait = 600
        start = time.time()
        while time.time() - start < max_wait:
            time.sleep(5)

            poll = requests.get(
                "https://apihub.agnes-ai.com/agnesapi",
                params={"video_id": video_id, "model_name": AGNES_MODEL},
                headers={"Authorization": f"Bearer {key}"},
                timeout=30,
            )

            if poll.status_code != 200:
                print(f"  Agnes poll HTTP {poll.status_code}, retrying...")
                continue

            result = poll.json()
            status = result.get("status")

            if status == "completed":
                video_url = (result.get("metadata") or {}).get("url") or result.get("video_url")
                if not video_url:
                    print(f"  Agnes completed but no URL: {result}")
                    return False

                print(f"  Agnes completed, downloading...")
                video_data = requests.get(video_url, timeout=300)
                with open(path, "wb") as f:
                    f.write(video_data.content)
                return True

            if status == "failed":
                print(f"  Agnes failed: {result.get('error', 'unknown')}")
                return False

            progress = result.get("progress", 0)
            print(f"  Agnes status: {status} ({progress}%)")

        print("  Agnes timed out")
        return False

    except Exception as exc:
        print(f"  Agnes error: {str(exc)[:250]}")
        return False


# ---------------------------------------------------------
# HuggingFace fallback
# ---------------------------------------------------------

def _hf_tokens():
    names = ["HF_TOKEN", "HF_TOKEN_2", "HF_TOKEN_3", "HF_TOKEN_4"]
    return [os.getenv(name, "").strip() for name in names if os.getenv(name, "").strip()]


def _find_video(obj):
    if isinstance(obj, str):
        if obj.lower().endswith((".mp4", ".webm", ".mov")) and os.path.exists(obj):
            return obj
        return None
    if isinstance(obj, dict):
        for key in ("video", "path", "value", "name"):
            if key in obj:
                result = _find_video(obj[key])
                if result:
                    return result
        for value in obj.values():
            result = _find_video(value)
            if result:
                return result
    if isinstance(obj, (list, tuple)):
        for value in obj:
            result = _find_video(value)
            if result:
                return result
    return None


def _pick_endpoint(api):
    endpoints = api.get("named_endpoints", {})
    best = None
    for name, endpoint in endpoints.items():
        params = endpoint.get("parameters", [])
        parameter_names = [p.get("parameter_name", "").lower() for p in params]
        if not any("prompt" in n and "negative" not in n for n in parameter_names):
            continue
        blocking = [p for p in params if not p.get("parameter_has_default") and "prompt" not in p.get("parameter_name", "").lower()]
        if blocking:
            continue
        score = ("text" in name.lower()) * 2 + ("video" in name.lower()) - ("image" in name.lower())
        if best is None or score > best[0]:
            best = (score, name, params)
    return best


def _choices(parameter):
    parameter_type = parameter.get("type")
    if isinstance(parameter_type, dict) and parameter_type.get("enum"):
        return [str(x) for x in parameter_type["enum"]]
    return re.findall(r"'([^']+)'", str(parameter.get("python_type", "")) + " " + str(parameter_type))


def _num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _build_kwargs(parameters, prompt, rich=True):
    kwargs = {}
    defaults = {p.get("parameter_name", ""): p.get("parameter_default") for p in parameters}
    for parameter in parameters:
        name = parameter.get("parameter_name", "")
        lower = name.lower()
        if "prompt" in lower and "negative" not in lower:
            kwargs[name] = prompt
        elif "negative" in lower:
            kwargs[name] = "text, subtitles, watermark, logo, human, deformed animal, extra limbs, duplicate character, blurry, low quality, 2D illustration, anime, sketch"
        elif "mode" in lower:
            choices = [c for c in _choices(parameter) if "text" in c.lower()]
            if choices:
                kwargs[name] = choices[0]
        elif rich and "duration" in lower and _num(parameter.get("parameter_default")):
            kwargs[name] = CLIP_SECONDS
    if rich:
        heights = [n for n in defaults if "height" in n.lower() and _num(defaults[n])]
        widths = [n for n in defaults if "width" in n.lower() and _num(defaults[n])]
        if heights and widths:
            height, width = heights[0], widths[0]
            if defaults[width] > defaults[height]:
                kwargs[height] = defaults[width]
                kwargs[width] = defaults[height]
    return kwargs


def hf_clip(prompt, path):
    tokens = _hf_tokens()
    if not tokens:
        print("  No HuggingFace token found.")
        return False

    try:
        from gradio_client import Client
    except Exception as exc:
        print("  gradio_client missing:", exc)
        return False

    for space in HF_SPACES:
        for token_index, token in enumerate(tokens):
            if (space, token_index) in _HF_DEAD:
                continue
            try:
                print(f"  HF Space {space} (token {token_index + 1})...")
                try:
                    client = Client(space, token=token, verbose=False)
                except TypeError:
                    client = Client(space, hf_token=token, verbose=False)

                api = client.view_api(return_format="dict", print_info=False)
                picked = _pick_endpoint(api)
                if not picked:
                    print("  No usable text-to-video endpoint.")
                    break

                _, endpoint, parameters = picked
                print("  Endpoint:", endpoint)
                video = None
                last_error = None

                for rich in (True, False):
                    kwargs = _build_kwargs(parameters, prompt, rich)
                    try:
                        result = client.submit(api_name=endpoint, **kwargs).result(timeout=900)
                    except Exception as exc:
                        last_error = exc
                        message = str(exc).lower()
                        print("  HF attempt failed:", str(exc)[:200])
                        if any(w in message for w in ("quota", "exceeded", "gpu", "limit", "401", "unauthorized")):
                            raise
                        continue
                    video = _find_video(result)
                    if video:
                        break

                if not video:
                    if last_error:
                        raise last_error
                    continue

                shutil.copyfile(video, path)
                return True

            except Exception as exc:
                message = str(exc)
                print("  HF failed:", message[:250])
                lower = message.lower()
                if any(w in lower for w in ("quota", "exceeded", "gpu", "limit", "unauthorized", "401")):
                    _HF_DEAD.add((space, token_index))
                    continue
                break

    return False


# ---------------------------------------------------------
# Image-motion fallback (last resort)
# ---------------------------------------------------------

def _pollinations_key():
    return os.getenv("POLLINATIONS_API_KEY", "").strip()


def _fetch_image(prompt, path, seed):
    key = _pollinations_key()
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    for attempt in range(3):
        response = requests.get(
            "https://gen.pollinations.ai/image/" + quote(prompt),
            params={"width": 720, "height": 1280, "model": "flux", "seed": seed, "nologo": "true"},
            headers=headers,
            timeout=180,
        )
        if response.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        response.raise_for_status()
        with open(path, "wb") as file:
            file.write(response.content)
        return
    raise RuntimeError("Pollinations rate limited.")


def _zoom_expression(move, frames):
    if move == 0:
        return "z='min(zoom+0.0022,1.32)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    if move == 1:
        return "z='1.18':x='(iw-iw/zoom)*on/" + str(frames) + "':y='ih/2-(ih/zoom/2)'"
    if move == 2:
        return "z='min(zoom+0.0028,1.38)':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*on/" + str(frames) + "'"
    if move == 3:
        return "z='1.22':x='(iw-iw/zoom)*(0.5+0.5*sin(on/" + str(frames) + "*PI))':y='ih/2-(ih/zoom/2)'"
    if move == 4:
        return "z='if(eq(on,1),1.28,min(zoom+0.002,1.4))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    return "z='if(eq(on,1),1.35,max(zoom-0.002,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"


CAMERA_MOVES = [
    "slow cinematic push in",
    "slow tracking movement from left to right",
    "dynamic low angle tracking shot",
    "gentle orbit around the character",
    "quick push toward the facial reaction",
    "slow pull back revealing the environment",
]


def image_motion_clip(prompt, path, seed):
    count = max(2, IMAGES_PER_SCENE)
    seconds = CLIP_SECONDS / count
    frames = max(1, int(seconds * 25))
    parts = []

    try:
        for index in range(count):
            image_path = f"{path}.{index}.jpg"
            part_path = f"{path}.{index}.mp4"
            camera = CAMERA_MOVES[index % len(CAMERA_MOVES)]

            frame_prompt = f"""
{prompt}

CINEMATIC FRAME:
This is one frame from a continuous animated short.
Preserve exactly the same characters and environment.

CAMERA:
{camera}

VISUAL QUALITY:
high-end cinematic 3D CGI,
realistic detailed fur,
natural anatomy,
expressive eyes,
cinematic lighting,
realistic shadows,
depth of field,
vertical 9:16 composition.

Do not add:
text, subtitles, watermark, logo,
humans, duplicate animals, extra limbs,
extra eyes, deformed faces, distorted paws,
cropped head, cropped body,
flat 2D art, anime, sketch.
"""
            _fetch_image(" ".join(frame_prompt.split()), image_path, seed)

            move = (seed + index) % len(CAMERA_MOVES)
            zoom = _zoom_expression(move, frames)

            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", image_path,
                "-vf", (
                    "scale=1440:2560:force_original_aspect_ratio=increase,"
                    "crop=1440:2560,"
                    f"zoompan={zoom}:d={frames}:s=1080x1920:fps=25"
                ),
                "-frames:v", str(frames),
                "-pix_fmt", "yuv420p",
                part_path,
            ], check=True)

            parts.append(part_path)
            time.sleep(2)

        list_path = path + ".txt"
        with open(list_path, "w", encoding="utf-8") as file:
            for part in parts:
                file.write("file '" + os.path.abspath(part) + "'\n")

        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", list_path,
            "-c", "copy", path,
        ], check=True)

        return True

    except Exception as exc:
        print("  Free image-motion failed:", str(exc)[:250])
        return False


# ---------------------------------------------------------
# Main clip generator
# ---------------------------------------------------------

def make_clip(prompt, path, seed=0):
    print(f"Generating clip: {path}")

    if FREE_MODE:
        print("  FREE_MODE enabled.")

        # Priority 1: fal.ai MiniMax H3 Max
        if fal_video(prompt, path):
            print("  Generated with fal.ai.")
            return True

        print("  fal.ai unavailable, trying Agnes...")

        # Priority 2: Agnes AI
        if agnes_video(prompt, path):
            print("  Generated with Agnes AI.")
            return True

        print("  Agnes unavailable, trying HuggingFace...")

        # Priority 3: HuggingFace
        if hf_clip(prompt, path):
            print("  Generated with HF video.")
            return True

        print("  All providers failed, using image-motion fallback...")

        # Priority 4: image + zoom
        return image_motion_clip(prompt, path, seed)

    # Non-free mode (Replicate)
    try:
        from .replicate_video import replicate_clip
        if replicate_clip(prompt, path):
            return True
    except Exception as exc:
        print("  Replicate unavailable:", str(exc)[:150])

    return image_motion_clip(prompt, path, seed)
