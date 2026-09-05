import os
import sys
import time
import requests
import subprocess

try:
    from gradio_client import Client
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False

# ==================== CONFIGURATION ====================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
HF_TOKENS = [
    os.getenv("HF_TOKEN", ""),
    os.getenv("HF_TOKEN_2", ""),
    os.getenv("HF_TOKEN_3", ""),
]
HF_TOKENS = [t for t in HF_TOKENS if t.strip()]
HF_SPACE = os.getenv("HF_VIDEO_SPACES", "Wan-AI/Wan2.1")
NUM_SCENES = int(os.getenv("NUM_SCENES", "4"))

YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN", "")
YT_PRIVACY_STATUS = os.getenv("YT_PRIVACY_STATUS", "public")

print("YouTube Shorts Visual Bot Initialized (No Voiceover).")

def generate_cat_prompts():
    """Generates funny/cool cat 3D animation prompts similar to popular reels."""
    prompts = [
        "A cute fat orange cat wearing a gold chain walking with a little duck, 3D Pixar style, cinematic lighting",
        "A cool fat orange cat wearing sunglasses riding a small motorcycle with a duck, funny, vibrant colors",
        "A happy fat orange cat wearing a chef hat cooking fried chicken in a kitchen pan, humorous 3D animation",
        "A fat orange cat wearing cool sunglasses dancing energetically with funny expressions, vibrant 3D style"
    ]
    return "Cute Cat Adventures", prompts

HF_INFERENCE_MODEL = os.getenv("HF_INFERENCE_MODEL", "damo-vilab/text-to-video-ms-1.7b")

def generate_animated_clip_inference_api(prompt_text, idx):
    """Generates a real (low-res) AI video clip using HF's official Inference API.
    More reliable than community Gradio Spaces, which frequently get paused/sleep."""
    if not HF_TOKENS:
        print("No HF tokens available for Inference API attempt.")
        return None

    api_url = f"https://api-inference.huggingface.co/models/{HF_INFERENCE_MODEL}"

    for token_idx, token in enumerate(HF_TOKENS):
        headers = {"Authorization": f"Bearer {token}"}
        try:
            print(f"Trying HF Inference API ('{HF_INFERENCE_MODEL}') Token #{token_idx + 1} for: {prompt_text[:40]}...")
            resp = requests.post(api_url, headers=headers, json={"inputs": prompt_text}, timeout=120)

            # Model may need to "warm up" on first call - HF returns 503 with an estimated_time.
            if resp.status_code == 503:
                try:
                    wait_s = min(float(resp.json().get("estimated_time", 20)), 40)
                except Exception:
                    wait_s = 20
                print(f"  -> model is loading, waiting {wait_s:.0f}s then retrying once...")
                time.sleep(wait_s)
                resp = requests.post(api_url, headers=headers, json={"inputs": prompt_text}, timeout=120)

            content_type = resp.headers.get("content-type", "")
            print(f"  -> status={resp.status_code} content-type={content_type} size={len(resp.content)}")

            if resp.status_code == 200 and len(resp.content) > 5000:
                output_file = f"scene_{idx}_hf.mp4"
                with open(output_file, "wb") as f:
                    f.write(resp.content)
                print(f"Successfully generated video clip {idx} via HF Inference API.")
                return output_file
            else:
                print(f"  -> Inference API did not return a usable video: {resp.text[:300]}")

        except Exception as e:
            print(f"  -> HF Inference API attempt failed: {e}")

    return None

def generate_animated_clip_hf(prompt_text, idx):
    """Generates a real AI video clip using Hugging Face Free Spaces using correct fn_index."""
    if not GRADIO_AVAILABLE:
        print("Gradio client not available.")
        return None

    tokens_to_try = HF_TOKENS if HF_TOKENS else [""]
    
    for token_idx, token in enumerate(tokens_to_try):
        for space_id in HF_SPACE.split(","):
            space_id = space_id.strip()
            try:
                print(f"Trying HF Space '{space_id}' using Token #{token_idx + 1} for prompt: {prompt_text[:30]}...")
                if token:
                    os.environ["HF_TOKEN"] = token
                
                client = Client(space_id)

                # Instead of guessing api_name/fn_index, ask the Space what it actually exposes.
                try:
                    api_info = client.view_api(print_info=False, return_format="dict")
                except Exception as api_err:
                    print(f"  -> could not read API spec: {api_err}")
                    api_info = {}

                def _extract_video_path(res):
                    """Return a usable file path from a predict() result, or None."""
                    candidates = res if isinstance(res, (list, tuple)) else [res]
                    for c in candidates:
                        # Gradio file outputs are often dicts like {'video': path} or {'path': path}
                        if isinstance(c, dict):
                            c = c.get("video") or c.get("path") or c.get("name")
                        if c and isinstance(c, str) and os.path.exists(c):
                            return c
                    return None

                def _try_endpoint(call_kwargs, label):
                    try:
                        print(f"  -> trying {label}")
                        res = client.predict(prompt_text, **call_kwargs)
                        preview = str(res)[:200]
                        print(f"     result type={type(res).__name__} value={preview}")
                        vp = _extract_video_path(res)
                        if vp:
                            return vp
                        print(f"     -> {label} did not return a usable video file, trying next endpoint")
                    except Exception as inner_e:
                        print(f"  -> {label} failed: {inner_e}")
                    return None

                video_path = None

                # 1) Try every named endpoint the Space actually has.
                named_endpoints = api_info.get("named_endpoints", {}) or {}
                for ep_name, ep_spec in named_endpoints.items():
                    param_names = [
                        p.get("label") or p.get("parameter_name") or "?"
                        for p in (ep_spec.get("parameters") or [])
                    ]
                    print(f"  -> named endpoint {ep_name} expects params: {param_names}")
                    video_path = _try_endpoint({"api_name": ep_name}, f"named endpoint {ep_name}")
                    if video_path:
                        break

                # 2) If nothing worked, try every unnamed endpoint (fn_index) it has.
                if not video_path:
                    unnamed_endpoints = api_info.get("unnamed_endpoints", {}) or {}
                    for fn_idx_str in unnamed_endpoints:
                        fn_idx = int(fn_idx_str)
                        video_path = _try_endpoint({"fn_index": fn_idx}, f"fn_index {fn_idx}")
                        if video_path:
                            break

                if video_path:
                    output_file = f"scene_{idx}_hf.mp4"
                    os.rename(str(video_path), output_file)
                    print(f"Successfully generated video clip {idx} via HF.")
                    return output_file
            except Exception as e:
                print(f"HF Space {space_id} with Token #{token_idx + 1} failed: {e}")
                continue
                
    print(f"Warning: HF failed for scene {idx}. Using fallback zoom-in effect.")
    return None

def create_fallback_video(prompt_text, idx):
    """Creates a basic zoom-in video using FFmpeg with safe connection handling."""
    output_file = f"scene_{idx}_fallback.mp4"
    img_path = f"scene_{idx}.jpg"

    img_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt_text)}?width=1080&height=1920&nologo=true"

    downloaded = False
    for attempt in range(3):  # 3 retry attempts
        try:
            print(f"Downloading fallback image for scene {idx} (Attempt {attempt+1})...")
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(img_url, headers=headers, timeout=30)
            if response.status_code == 200 and len(response.content) > 1000:
                with open(img_path, "wb") as handler:
                    handler.write(response.content)
                downloaded = True
                break
            else:
                print(f"  -> bad response: status={response.status_code} size={len(response.content)}")
        except Exception as e:
            print(f"Download attempt {attempt+1} failed: {e}")
            time.sleep(2)

    # Agar download fail ho jaye toh solid color/blank frame create kar lo taake script crash na ho
    if not downloaded or not os.path.exists(img_path):
        print(f"Creating emergency solid color frame for scene {idx}...")
        color_cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=orange:s=1080:1920", "-vframes", "1", img_path]
        color_result = subprocess.run(color_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if color_result.returncode != 0 or not os.path.exists(img_path):
            print(f"  -> even emergency frame creation failed: {color_result.stderr.decode(errors='ignore')[:500]}")
            return None

    # Vary the "camera move" per scene so all 4 clips don't feel identical:
    # alternate between zoom-in-center, pan-left-to-right, and pan-right-to-left.
    camera_moves = [
        "zoompan=z='min(zoom+0.0015,1.4)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1080x1920",
        "zoompan=z='min(zoom+0.0012,1.3)':x='if(gte(zoom,1.3),x,x+1)':y='ih/2-(ih/zoom/2)':d=125:s=1080x1920",
        "zoompan=z='min(zoom+0.0012,1.3)':x='if(gte(zoom,1.3),x,x-1)':y='ih/2-(ih/zoom/2)':d=125:s=1080x1920",
    ]
    camera_move = camera_moves[idx % len(camera_moves)]

    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", img_path,
        "-t", "5",
        "-vf", f"scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,{camera_move}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", output_file
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0 or not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
        print(f"FFmpeg failed to build fallback clip for scene {idx}: {result.stderr.decode(errors='ignore')[:800]}")
        return None

    return output_file

def get_video_duration(path):
    """Returns duration in seconds via ffprobe, or None on failure."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return float(result.stdout.decode().strip())
    except Exception as e:
        print(f"Could not read video duration: {e}")
        return None

# Free, Creative Commons (CC BY 4.0) background tracks by Kevin MacLeod / incompetech.com.
# Rotated by day-of-year so consecutive posts don't all sound identical.
BACKGROUND_MUSIC_TRACKS = [
    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Monkeys%20Spinning%20Monkeys.mp3",
    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Wallpaper.mp3",
    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Carefree.mp3",
]

def add_background_music(video_path, output_path):
    """Downloads a free CC-BY track and mixes it under the video. Returns output_path, or
    the original video_path unchanged if music could not be added (never fails the run)."""
    duration = get_video_duration(video_path)
    if not duration:
        print("Skipping background music: could not determine video duration.")
        return video_path

    day_index = int(time.strftime("%j"))
    track_url = BACKGROUND_MUSIC_TRACKS[day_index % len(BACKGROUND_MUSIC_TRACKS)]
    music_path = "bg_music.mp3"

    try:
        print(f"Downloading background music: {track_url}")
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(track_url, headers=headers, timeout=30)
        if resp.status_code != 200 or len(resp.content) < 1000:
            print(f"  -> music download failed (status={resp.status_code}), continuing without music.")
            return video_path
        with open(music_path, "wb") as f:
            f.write(resp.content)
    except Exception as e:
        print(f"  -> music download error: {e}, continuing without music.")
        return video_path

    fade_out_start = max(duration - 1, 0)
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-stream_loop", "-1", "-i", music_path,
        "-filter_complex",
        f"[1:a]atrim=0:{duration},volume=0.35,afade=t=out:st={fade_out_start}:d=1[aud]",
        "-map", "0:v", "-map", "[aud]",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        output_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        print(f"Adding background music failed, uploading silent video instead: "
              f"{result.stderr.decode(errors='ignore')[:800]}")
        return video_path

    print("Background music added successfully.")
    return output_path

def upload_to_youtube(video_path, title, description, tags=None):
    """Uploads the generated Short to YouTube using the stored refresh token."""
    if not YOUTUBE_AVAILABLE:
        print("google-api-python-client not installed - skipping YouTube upload.")
        return None

    if not (YT_CLIENT_ID and YT_CLIENT_SECRET and YT_REFRESH_TOKEN):
        print("YouTube credentials (YT_CLIENT_ID/YT_CLIENT_SECRET/YT_REFRESH_TOKEN) not set - skipping upload.")
        return None

    if not os.path.exists(video_path):
        print(f"Cannot upload: {video_path} not found.")
        return None

    try:
        creds = Credentials(
            token=None,
            refresh_token=YT_REFRESH_TOKEN,
            client_id=YT_CLIENT_ID,
            client_secret=YT_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )

        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": tags or [],
                "categoryId": "22",  # People & Blogs; fine for general Shorts content
            },
            "status": {
                "privacyStatus": YT_PRIVACY_STATUS,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        print(f"Uploading '{title}' to YouTube...")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  Upload progress: {int(status.progress() * 100)}%")

        video_id = response.get("id")
        print(f"Successfully uploaded to YouTube! Video ID: {video_id}")
        print(f"Watch it here: https://youtube.com/shorts/{video_id}")
        return video_id

    except Exception as e:
        print(f"YouTube upload failed: {e}")
        return None

def main():
    title, scene_prompts = generate_cat_prompts()

    if not HF_TOKENS:
        print("No HF tokens set - skipping AI video generation attempts, using fallback images only.")

    video_clips = []
    for idx, prompt in enumerate(scene_prompts[:NUM_SCENES]):
        clip = generate_animated_clip_inference_api(prompt, idx)
        if not clip and HF_SPACE.strip():
            clip = generate_animated_clip_hf(prompt, idx)
        if not clip:
            clip = create_fallback_video(prompt, idx)
        if clip and os.path.exists(clip):
            video_clips.append(clip)
        else:
            print(f"Warning: scene {idx} produced no usable clip at all - skipping it.")

    if not video_clips:
        print("Fatal: no video clips were produced for any scene. Aborting.")
        sys.exit(1)

    with open("clips.txt", "w") as f:
        for clip in video_clips:
            f.write(f"file '{clip}'\n")

    final_video = "final_output.mp4"
    print("Merging video clips into final short...")
    merge_result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "clips.txt", "-c", "copy", final_video],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    if merge_result.returncode != 0 or not os.path.exists(final_video) or os.path.getsize(final_video) == 0:
        print(f"Fatal: merging clips into {final_video} failed.")
        print(merge_result.stderr.decode(errors="ignore")[:1500])
        sys.exit(1)

    print(f"Success! Short video generated: {final_video}")

    music_video = add_background_music(final_video, "final_with_music.mp4")
    upload_video_path = music_video

    video_title = f"{title} #Shorts"
    video_description = (
        f"{title} - daily cute cat short! \n\n#Shorts #cats #cute #funny #animation"
    )
    if music_video != final_video:
        video_description += "\n\nMusic: Kevin MacLeod (incompetech.com) - Licensed under CC BY 4.0"
    video_tags = ["cats", "shorts", "funny", "cute", "animals", "3d animation"]

    video_id = upload_to_youtube(upload_video_path, video_title, video_description, video_tags)
    if not video_id:
        print("Fatal: video was generated but the YouTube upload did not succeed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
