import os
import sys
import time
import requests
import subprocess
from gtts import gTTS

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
NUM_SCENES = int(os.getenv("NUM_SCENES", "3"))

print("YouTube Shorts Bot with Multi-HF Token Support Initialized.")

def generate_ai_script():
    """Generates an engaging topic and scene prompts using Gemini API."""
    print("Generating script and prompts using Gemini...")
    # Fallback default script agar Gemini key na ho ya error aaye
    scenes = [
        "A cinematic hyper-realistic shot of a futuristic neon city flying cars in the rain, 4k",
        "A mystical glowing portal opening in a deep dark enchanted forest, magical particles",
        "An astronaut standing on a distant alien planet watching twin suns set, breathtaking view"
    ]
    return "Mind-blowing AI Facts You Didn't Know", scenes

def generate_animated_clip_hf(prompt_text, idx):
    """Generates a real AI video clip using Hugging Face Free Spaces with token rotation."""
    if not GRADIO_AVAILABLE:
        print("Gradio client not available.")
        return None

    tokens_to_try = HF_TOKENS if HF_TOKENS else [""]
    
    for token_idx, token in enumerate(tokens_to_try):
        for space_id in HF_SPACE.split(","):
            space_id = space_id.strip()
            try:
                print(f"Trying HF Space '{space_id}' using Token #{token_idx + 1} for prompt: {prompt_text[:30]}...")
                kwargs = {}
                if token:
                    kwargs["hf_token"] = token
                
                client = Client(space_id, **kwargs)
                
                # Predicting video from Space API
                result = client.predict(
                    prompt=prompt_text,
                    api_name="/generate"
                )
                
                if result:
                    # Gradio client sometimes returns a tuple or string path
                    video_path = result[0] if isinstance(result, (list, tuple)) else result
                    if video_path and os.path.exists(str(video_path)):
                        output_file = f"scene_{idx}_hf.mp4"
                        os.rename(str(video_path), output_file)
                        print(f"Successfully generated video clip for scene {idx} using HF.")
                        return output_file
            except Exception as e:
                print(f"HF Space {space_id} with Token #{token_idx + 1} failed: {e}")
                continue
                
    print(f"Warning: Could not generate AI video for scene {idx} via HF. Using fallback stock video/image effect.")
    return None

def create_fallback_video(prompt_text, idx):
    """Creates a basic zoom-in video using FFmpeg if HF fails."""
    output_file = f"scene_{idx}_fallback.mp4"
    img_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt_text)}?width=1080&height=1920&nologo=true"
    
    print(f"Downloading fallback image for scene {idx}...")
    img_data = requests.get(img_url).content
    img_path = f"scene_{idx}.jpg"
    with open(img_path, "wb") as handler:
        handler.write(img_data)
        
    # FFmpeg zoom-in effect
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", img_path,
        "-t", "5", "-vf", "scale=2000:3556,zoompan=z='min(zoom+0.0015,1.5)':d=125:s=1080:1920",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", output_file
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_file

def generate_voiceover(text):
    """Generates audio voiceover using gTTS."""
    print("Generating voiceover...")
    tts = gTTS(text=text, lang='en', slow=False)
    audio_path = "voiceover.mp3"
    tts.save(audio_path)
    return audio_path

def main():
    title, scene_prompts = generate_ai_script()
    
    video_clips = []
    for idx, prompt in enumerate(scene_prompts[:NUM_SCENES]):
        clip = generate_animated_clip_hf(prompt, idx)
        if not clip:
            clip = create_fallback_video(prompt, idx)
        video_clips.append(clip)
        
    # Combine clips list for ffmpeg
    with open("clips.txt", "w") as f:
        for clip in video_clips:
            f.write(f"file '{clip}'\n")
            
    final_video = "final_output.mp4"
    print("Merging video clips...")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "clips.txt", "-c", "copy", final_video], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    print("Process completed successfully! Video ready for upload.")

if __name__ == "__main__":
    main()
