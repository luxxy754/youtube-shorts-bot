"""Scene clip generation: Replicate -> Pollinations video -> Pollinations image + zoom."""
import os
import shutil
import subprocess
import time
from urllib.parse import quote

import requests

CLIP_SECONDS = int(os.getenv("CLIP_SECONDS", "5"))
# Comma separated, tried in order. Change without touching code.
VIDEO_MODELS = [m.strip() for m in os.getenv(
    "VIDEO_MODELS", "bytedance/seedance-1-lite,minimax/video-01").split(",") if m.strip()]
# Replicate accounts without much credit allow only 1 request per ~10s.
REPLICATE_GAP = int(os.getenv("REPLICATE_GAP", "12"))

_replicate_dead = False  # set when credit is exhausted, so we stop wasting time


def _inputs(model, prompt):
    if model.startswith("bytedance/seedance"):
        full = {"prompt": prompt, "duration": CLIP_SECONDS, "resolution": "720p",
                "aspect_ratio": "9:16", "fps": 24}
    elif model.startswith("minimax/"):
        full = {"prompt": prompt, "prompt_optimizer": True}
    else:
        full = {"prompt": prompt, "aspect_ratio": "9:16"}
    return [full, {"prompt": prompt}]  # second = bare minimum if params are rejected


def _save(output, path):
    if isinstance(output, (list, tuple)):
        output = output[0]
    if hasattr(output, "read"):
        data = output.read()
    else:
        r = requests.get(str(output), timeout=300)
        r.raise_for_status()
        data = r.content
    with open(path, "wb") as f:
        f.write(data)


def replicate_clip(prompt, path):
    global _replicate_dead
    if _replicate_dead or not os.getenv("REPLICATE_API_TOKEN"):
        return False
    import replicate
    for model in VIDEO_MODELS:
        for inp in _inputs(model, prompt):
            for attempt in range(2):
                try:
                    print(f"  Replicate {model} ...")
                    _save(replicate.run(model, input=inp), path)
                    time.sleep(REPLICATE_GAP)
                    return True
                except Exception as exc:  # noqa: BLE001
                    msg = str(exc)
                    status = getattr(exc, "status", None)
                    if status == 402 or "Insufficient credit" in msg:
                        print("  Replicate has NO CREDIT. Add billing at "
                              "https://replicate.com/account/billing - skipping Replicate.")
                        _replicate_dead = True
                        return False
                    if status == 429 or "throttled" in msg:
                        print(f"  Rate limited, waiting {REPLICATE_GAP + 8}s and retrying")
                        time.sleep(REPLICATE_GAP + 8)
                        continue
                    print(f"  {model} failed: {msg[:200]}")
                    break
    return False



# ---------------------------------------------------------------- Hugging Face (free)
HF_SPACES = [x.strip() for x in os.getenv(
    "HF_VIDEO_SPACES", "Lightricks/ltx-video-distilled,Wan-AI/Wan2.1").split(",") if x.strip()]
_hf_dead = set()  # (space, token_index) that ran out of quota


def _hf_tokens():
    names = ["HF_TOKEN", "HF_TOKEN_2", "HF_TOKEN_3", "HF_TOKEN_4"]
    return [os.getenv(n, "").strip() for n in names if os.getenv(n, "").strip()]


def _find_video(obj):
    """Recursively find a video file path in a gradio result."""
    if isinstance(obj, str):
        return obj if obj.lower().endswith((".mp4", ".webm", ".mov")) and os.path.exists(obj) else None
    if isinstance(obj, dict):
        for k in ("video", "path", "value", "name"):
            if k in obj:
                found = _find_video(obj[k])
                if found:
                    return found
        for v in obj.values():
            found = _find_video(v)
            if found:
                return found
    if isinstance(obj, (list, tuple)):
        for v in obj:
            found = _find_video(v)
            if found:
                return found
    return None


def _pick_endpoint(api):
    """Choose the text->video endpoint from a Space's API description."""
    eps = api.get("named_endpoints", {})
    best = None
    for name, ep in eps.items():
        params = ep.get("parameters", [])
        pnames = [p.get("parameter_name", "").lower() for p in params]
        if not any("prompt" in n and "negative" not in n for n in pnames):
            continue
        # every parameter without a default must be something we can fill (the prompt)
        blocking = [p for p in params if not p.get("parameter_has_default")
                    and "prompt" not in p.get("parameter_name", "").lower()]
        if blocking:
            continue
        score = ("text" in name.lower()) * 2 + ("video" in name.lower()) - ("image" in name.lower())
        if best is None or score > best[0]:
            best = (score, name, params)
    return best


def hf_clip(prompt, path):
    tokens = _hf_tokens()
    if not tokens:
        return False
    try:
        from gradio_client import Client
    except Exception as exc:  # noqa: BLE001
        print(f"  gradio_client missing: {exc}")
        return False
    for space in HF_SPACES:
        for ti, token in enumerate(tokens):
            if (space, ti) in _hf_dead:
                continue
            try:
                print(f"  HF Space {space} (token {ti + 1}) ...")
                try:
                    client = Client(space, token=token, verbose=False)  # newer gradio_client
                except TypeError:
                    client = Client(space, hf_token=token, verbose=False)  # older versions
                api = client.view_api(return_format="dict", print_info=False)
                pick = _pick_endpoint(api)
                if not pick:
                    print("  no usable text->video endpoint, skipping Space")
                    break
                _, name, params = pick
                kwargs = {}
                for prm in params:
                    pn = prm.get("parameter_name", "")
                    if "prompt" in pn.lower() and "negative" not in pn.lower():
                        kwargs[pn] = prompt
                result = client.submit(api_name=name, **kwargs).result(timeout=900)
                video = _find_video(result)
                if not video:
                    print(f"  no video in result: {str(result)[:150]}")
                    break
                shutil.copyfile(video, path)
                return True
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                print(f"  HF failed: {msg[:220]}")
                if any(w in msg.lower() for w in ("quota", "exceeded", "gpu", "limit", "unauthorized", "401")):
                    _hf_dead.add((space, ti))
                    continue  # try next token
                break  # other error: try next Space
    return False


def _pollinations_key():
    return os.getenv("POLLINATIONS_API_KEY", "").strip()


def pollinations_video(prompt, path):
    """Pollinations video API (uses your Pollen balance). Unverified model availability."""
    key = _pollinations_key()
    if not key:
        return False
    try:
        r = requests.get(
            "https://gen.pollinations.ai/video/" + quote(prompt),
            params={"duration": CLIP_SECONDS, "aspectRatio": "9:16"},
            headers={"Authorization": f"Bearer {key}"}, timeout=420)
        r.raise_for_status()
        if "video" not in r.headers.get("content-type", "video"):
            raise RuntimeError(f"unexpected content-type {r.headers.get('content-type')}")
        with open(path, "wb") as f:
            f.write(r.content)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  Pollinations video failed: {str(exc)[:200]}")
        return False


SHOTS = [
    "wide establishing shot",
    "close-up shot of the characters' faces and funny reactions",
    "dynamic low angle action shot",
]
IMAGES_PER_SCENE = int(os.getenv("IMAGES_PER_SCENE", "2"))
FREE_MODE = os.getenv("FREE_MODE", "0").lower() in {"1", "true", "yes"}


def _move(kind, frames):
    """ffmpeg zoompan expression for one camera move."""
    cx, cy = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'", None
    if kind == 0:  # slow zoom in
        return f"z='min(zoom+0.0018,1.3)':{cx}"
    if kind == 1:  # pan left -> right
        return f"z=1.25:x='(iw-iw/zoom)*on/{frames}':y='ih/2-(ih/zoom/2)'"
    if kind == 2:  # zoom out
        return f"z='if(eq(on,1),1.3,max(zoom-0.0018,1.0))':{cx}"
    return f"z=1.25:x='(iw-iw/zoom)*(1-on/{frames})':y='ih/2-(ih/zoom/2)'"  # pan right -> left


def _fetch_image(prompt, path, seed):
    key = _pollinations_key()
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    for attempt in range(3):
        r = requests.get(
            "https://gen.pollinations.ai/image/" + quote(prompt),
            params={"width": 720, "height": 1280, "model": "flux", "seed": seed},
            headers=headers, timeout=180)
        if r.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
        return
    raise RuntimeError("Pollinations rate limited")


def image_motion_clip(prompt, path, seed):
    """Free mode: several Pixar-style images with different camera moves = one scene clip."""
    n = max(1, IMAGES_PER_SCENE)
    seconds = CLIP_SECONDS / n
    frames = int(seconds * 25)
    parts = []
    try:
        for k in range(n):
            img = f"{path}.{k}.jpg"
            part = f"{path}.{k}.mp4"
            _fetch_image(f"{prompt} {SHOTS[k % len(SHOTS)]}", img, seed + k)
            zp = _move((seed + k) % 4, frames)
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error", "-i", img, "-vf",
                f"scale=1440:2560:force_original_aspect_ratio=increase,crop=1440:2560,"
                f"zoompan={zp}:d={frames}:s=1080x1920:fps=25",
                "-frames:v", str(frames), "-pix_fmt", "yuv420p", part], check=True)
            parts.append(part)
            time.sleep(3)  # be nice to the free API
        lst = path + ".txt"
        with open(lst, "w") as f:
            for part in parts:
                f.write(f"file '{os.path.abspath(part)}'\n")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", lst, "-c", "copy", path], check=True)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  Pollinations image failed: {str(exc)[:200]}")
        return False


def make_clip(prompt, path, seed=0):
    if FREE_MODE:
        if hf_clip(prompt, path):
            return True
        print("  HF video unavailable (quota?), using free image + camera motion for this scene")
    else:
        if replicate_clip(prompt, path):
            return True
        if os.getenv("POLLINATIONS_VIDEO", "0") == "1":
            print("  Trying Pollinations video")
            if pollinations_video(prompt, path):
                return True
        print("  Falling back to free image + camera motion")
    return image_motion_clip(prompt, path, seed)
