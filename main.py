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
    for attempt in range(3): # 3 retry attempts
        try:
            print(f"Downloading fallback image for scene {idx} (Attempt {attempt+1})...")
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(img_url, headers=headers, timeout=30)
            if response.status_code == 200:
                with open(img_path, "wb") as handler:
                    handler.write(response.content)
                downloaded = True
                break
        except Exception as e:
            print(f"Download attempt {attempt+1} failed: {e}")
            time.sleep(2)
            
    # Agar download fail ho jaye toh solid color/blank frame create kar lo taake script crash na ho
    if not downloaded or not os.path.exists(img_path):
        print(f"Creating emergency solid color frame for scene {idx}...")
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=orange:s=1080:1920", "-vframes", "1", img_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", img_path,
        "-t", "5", "-vf", "scale=2000:3556,zoompan=z='min(zoom+0.0015,1.5)':d=125:s=1080:1920",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", output_file
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_file

def main():
    title, scene_prompts = generate_cat_prompts()
    
    video_clips = []
    for idx, prompt in enumerate(scene_prompts[:NUM_SCENES]):
        clip = generate_animated_clip_hf(prompt, idx)
        if not clip:
            clip = create_fallback_video(prompt, idx)
        video_clips.append(clip)
        
    with open("clips.txt", "w") as f:
        for clip in video_clips:
            f.write(f"file '{clip}'\n")
            
    final_video = "final_output.mp4"
    print("Merging video clips into final short...")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "clips.txt", "-c", "copy", final_video], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    print(f"Success! Short video generated: {final_video}")

if __name__ == "__main__":
    main()
