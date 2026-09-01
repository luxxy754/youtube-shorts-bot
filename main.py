import os
import time
import requests
from gtts import gTTS

# New Gemini SDK Import
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Warning: google-genai module not installed. Using fallback script.")

# ==========================================
# 1. API KEYS SETUP
# ==========================================
HEDRA_API_KEY = os.getenv("HEDRA_API_KEY", "your_hedra_api_key_here")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your_gemini_api_key_here")

# Initialize Gemini Client
client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Client Init Warning: {e}")

# Hedra API Config
HEDRA_BASE_URL = "https://api.hedra.com/web-app/public"
HEADERS = {
    "X-API-Key": HEDRA_API_KEY,
    "Authorization": f"Bearer {HEDRA_API_KEY}",
    "Content-Type": "application/json"
}


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def generate_script():
    """Gemini AI se Short Hindi Script generate karne ke liye"""
    print("Generating Hindi Script...")
    if not client:
        print("Gemini Client unavailable. Using default fallback script.")
        return "Haan bhai, chai peele pehle, kaam toh hota rahega!"

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Write a very short, funny 1-line joke in Hindi (Hinglish script) for a YouTube Short character. Keep it under 15 words."
        )
        script_text = response.text.strip()
        print(f"Generated Script: {script_text}")
        return script_text
    except Exception as e:
        print(f"Gemini Script Error (Using fallback): {e}")
        return "Haan bhai, chai peele pehle, kaam toh hota rahega!"


def generate_audio(text, output_file="hindi_audio.mp3"):
    """gTTS ke zariye Hindi Audio File (.mp3) banane ke liye"""
    print("Generating Hindi Audio via gTTS...")
    tts = gTTS(text=text, lang="hi", slow=False)
    tts.save(output_file)
    print(f"Audio saved to: {output_file}")
    return output_file


def generate_image_url():
    """Pollinations AI se Character Image Link banane ke liye"""
    print("Generating 3D Character Image URL via Pollinations AI...")
    prompt = "3d Pixar style funny character, cute male character talking, front facing portrait, high quality"
    image_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=720&height=1280&nologo=true"
    print(f"Image URL: {image_url}")
    return image_url


def generate_hedra_video(audio_file_path, image_url):
    """Hedra API flow: Audio upload -> Character Job Submit -> Status Check -> Download Video"""
    print("\n--- Starting Hedra Video Generation ---")

    # Step A: Audio Asset Upload
    print("Uploading Audio to Hedra...")
    upload_url = f"{HEDRA_BASE_URL}/assets"
    upload_headers = {
        "X-API-Key": HEDRA_API_KEY,
        "Authorization": f"Bearer {HEDRA_API_KEY}"
    }

    try:
        with open(audio_file_path, "rb") as f:
            files = {"file": ("audio.mp3", f, "audio/mpeg")}
            data = {"type": "audio"}
            upload_res = requests.post(
                upload_url, headers=upload_headers, files=files, data=data
            )
    except Exception as e:
        print(f"File reading error: {e}")
        return None

    if upload_res.status_code not in [200, 201]:
        print(f"Audio upload failed! Code: {upload_res.status_code}")
        print(f"Response: {upload_res.text}")
        return None

    audio_data = upload_res.json()
    audio_asset_id = audio_data.get("id") or audio_data.get("url")
    print(f"Audio Uploaded. Asset Identifier: {audio_asset_id}")

    # Step B: Submit Video Generation Job
    print("Submitting Character Generation Request...")
    generate_url = f"{HEDRA_BASE_URL}/generations"
    payload = {
        "type": "video",
        "input": {
            "aspect_ratio": "9:16",
            "audio_url": audio_asset_id,
            "image_url": image_url
        }
    }

    gen_res = requests.post(generate_url, json=payload, headers=HEADERS)

    if gen_res.status_code not in [200, 201]:
        print(f"Generation Job Failed! Code: {gen_res.status_code}")
        print(f"Response: {gen_res.text}")
        return None

    job_id = gen_res.json().get("job_id") or gen_res.json().get("id")
    print(f"Job Submitted Successfully. Job ID: {job_id}")

    # Step C: Polling Video Processing Status
    status_url = f"{HEDRA_BASE_URL}/generations/{job_id}"

    while True:
        status_res = requests.get(status_url, headers=HEADERS).json()
        job_status = status_res.get("status")

        if job_status == "completed":
            video_url = status_res.get("video_url") or status_res.get("url")
            print(f"\nSUCCESS: Video URL: {video_url}")

            video_data = requests.get(video_url).content
            output_video = "final_short.mp4"
            with open(output_video, "wb") as f:
                f.write(video_data)
            print(f"Saved locally as '{output_video}'")
            return output_video

        elif job_status in ["failed", "error"]:
            print(f"\nFAILED: Generation Error: {status_res.get('error')}")
            return None

        print("Processing video... Waiting 5 seconds.")
        time.sleep(5)


# ==========================================
# 3. MAIN EXECUTION PIPELINE
# ==========================================
if __name__ == "__main__":
    print("=== YouTube Shorts Automation Bot Started ===")

    # 1. Script Generation
    script_text = generate_script()

    # 2. Audio Generation
    audio_path = generate_audio(script_text)

    # 3. Image URL Generation
    image_url = generate_image_url()

    # 4. Hedra Video Generation & Artifact Save
    result = generate_hedra_video(audio_path, image_url)

    if result:
        print("\n=== Workflow Completed Successfully! ===")
    else:
        print("\n=== Workflow Failed at Video Generation Stage ===")
