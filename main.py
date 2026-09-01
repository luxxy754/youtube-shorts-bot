import os
import time
import requests
from gtts import gTTS

# Gemini SDK Setup
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Warning: google-genai module not installed.")

# Hedra SDK Setup
try:
    from hedra import HedraClient
    HEDRA_SDK_AVAILABLE = True
except ImportError:
    HEDRA_SDK_AVAILABLE = False

# ==========================================
# 1. API KEYS SETUP
# ==========================================
HEDRA_API_KEY = os.getenv("HEDRA_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Client Init Warning: {e}")


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def generate_script():
    print("Generating Hindi Script...")
    if not client:
        return "हां भाई, चाय पी लो पहले, काम तो होता रहेगा!"

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Write a very short, funny 1-line joke in Hindi (Devanagari script) for a YouTube Short character. Keep it under 15 words."
        )
        script_text = response.text.strip()
        print(f"Generated Script: {script_text}")
        return script_text
    except Exception as e:
        print(f"Gemini Script Error: {e}")
        return "हां भाई, चाय पी लो पहले, काम तो होता रहेगा!"


def generate_audio(text, output_file="hindi_audio.mp3"):
    print("Generating Hindi Audio via gTTS...")
    tts = gTTS(text=text, lang="hi", slow=False)
    tts.save(output_file)
    print(f"Audio saved to: {output_file}")
    return output_file


def generate_image_url():
    print("Generating 3D Character Image URL...")
    prompt = "3d Pixar style funny character, cute male character talking, front facing portrait, high quality"
    image_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=720&height=1280&nologo=true"
    print(f"Image URL: {image_url}")
    return image_url


def generate_hedra_video(audio_file_path, image_url):
    print("\n--- Starting Hedra Video Generation ---")
    
    if not HEDRA_SDK_AVAILABLE:
        print("Hedra SDK is not installed. Please add 'hedra' to your requirements/workflow.")
        return None

    try:
        hedra_client = HedraClient(api_key=HEDRA_API_KEY)

        # Upload Audio Asset via Official SDK
        print("Uploading Audio to Hedra via SDK...")
        audio_asset = hedra_client.audio.upload(file_path=audio_file_path)
        print(f"Audio Upload Success: {audio_asset}")

        # Generate Character Video
        print("Generating Character Video...")
        project = hedra_client.characters.create(
            avatar_image_url=image_url,
            audio_id=audio_asset.id,
            aspect_ratio="9:16"
        )
        
        job_id = project.id
        print(f"Job Created Successfully: {job_id}")

        # Wait for Completion
        max_retries = 36
        attempts = 0
        while attempts < max_retries:
            attempts += 1
            status_data = hedra_client.projects.get(job_id)
            status = status_data.status

            if status == "completed":
                video_url = status_data.video_url
                print(f"\nSUCCESS: Video URL: {video_url}")
                
                download_res = requests.get(video_url)
                if download_res.status_code == 200:
                    output_video = "final_short.mp4"
                    with open(output_video, "wb") as f:
                        f.write(download_res.content)
                    print(f"Saved locally as '{output_video}'")
                    return output_video
            elif status in ["failed", "error"]:
                print(f"Generation Failed: {status_data}")
                return None

            print(f"Processing... ({attempts}/{max_retries}). Waiting 5s.")
            time.sleep(5)

    except Exception as e:
        print(f"Hedra SDK Exception: {e}")
        return None

    return None


# ==========================================
# 3. MAIN EXECUTION PIPELINE
# ==========================================
if __name__ == "__main__":
    print("=== YouTube Shorts Automation Bot Started ===")

    script_text = generate_script()
    local_audio_path = generate_audio(script_text)
    image_url = generate_image_url()
    
    result = generate_hedra_video(local_audio_path, image_url)

    if result:
        print("\n=== Workflow Completed Successfully! ===")
    else:
        print("\n=== Workflow Failed ===")
