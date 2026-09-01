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
    print("Warning: google-genai module not installed. Using fallback script.")

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

HEDRA_BASE_URL = "https://api.hedra.com/v1"


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def generate_script():
    """Gemini AI se Short Hindi Script generate karne ke liye"""
    print("Generating Hindi Script...")
    if not client:
        print("Gemini Client unavailable. Using default fallback script.")
        return "हां भाई, चाय पी लो पहले, काम तो होता रहेगा!"

    try:
        # Devanagari script requested for accurate gTTS voice
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents="Write a very short, funny 1-line joke in Hindi (Devanagari script) for a YouTube Short character. Keep it under 15 words."
        )
        script_text = response.text.strip()
        print(f"Generated Script: {script_text}")
        return script_text
    except Exception as e:
        print(f"Gemini Script Error (Using fallback): {e}")
        return "हां भाई, चाय पी लो पहले, काम तो होता रहेगा!"


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
    """Hedra V3 API flow: Audio upload -> Character Job Submit -> Download Video"""
    print("\n--- Starting Hedra Video Generation ---")

    headers = {
        "X-API-Key": HEDRA_API_KEY,
        "Authorization": f"Bearer {HEDRA_API_KEY}"
    }

    # Step A: Audio Asset Upload
    print("Uploading Audio to Hedra...")
    upload_url = f"{HEDRA_BASE_URL}/audio"

    try:
        with open(audio_file_path, "rb") as f:
            files = {"file": ("audio.mp3", f, "audio/mpeg")}
            upload_res = requests.post(upload_url, headers=headers, files=files)
    except Exception as e:
        print(f"File reading error: {e}")
        return None

    if upload_res.status_code not in [200, 201]:
        print(f"Audio upload failed! Code: {upload_res.status_code}")
        print(f"Response: {upload_res.text}")
        return None

    audio_data = upload_res.json()
    audio_url = audio_data.get("url") or audio_data.get("id")
    print(f"Audio Uploaded Successfully. URL/ID: {audio_url}")

    # Step B: Submit Video Generation Job
    print("Submitting Character Generation Request...")
    generate_url = f"{HEDRA_BASE_URL}/characters"
    payload = {
        "aspect_ratio": "9:16",
        "audio_url": audio_url,
        "image_url": image_url
    }

    json_headers = {**headers, "Content-Type": "application/json"}
    gen_res = requests.post(generate_url, json=payload, headers=json_headers)

    if gen_res.status_code not in [200, 201]:
        print(f"Generation Job Failed! Code: {gen_res.status_code}")
        print(f"Response: {gen_res.text}")
        return None

    job_data = gen_res.json()
    job_id = job_data.get("job_id") or job_data.get("id")
    print(f"Job Submitted Successfully. Job ID: {job_id}")

    # Step C: Polling Processing Status with Timeout Guard
    status_url = f"{HEDRA_BASE_URL}/projects/{job_id}"
    max_retries = 30  # Max 2.5 minutes wait time
    attempts = 0

    while attempts < max_retries:
        attempts += 1
        status_res = requests.get(status_url, headers=headers)
        
        if status_res.status_code != 200:
            print(f"Status check error ({status_res.status_code}): {status_res.text}")
            time.sleep(5)
            continue

        res_json = status_res.json()
        job_status = res_json.get("status")

        if job_status == "completed":
            video_url = res_json.get("video_url") or res_json.get("url")
            print(f"\nSUCCESS: Video URL: {video_url}")

            download_res = requests.get(video_url)
            if download_res.status_code == 200:
                output_video = "final_short.mp4"
                with open(output_video, "wb") as f:
                    f.write(download_res.content)
                print(f"Saved locally as '{output_video}'")
                return output_video
            else:
                print("Failed to download video file from URL.")
                return None

        elif job_status in ["failed", "error"]:
            print(f"\nFAILED: Generation Error: {res_json.get('error')}")
            return None

        print(f"Processing status: '{job_status}' (Attempt {attempts}/{max_retries})... Waiting 5s.")
        time.sleep(5)

    print("Polling timed out! Video generation took too long.")
    return None


# ==========================================
# 3. MAIN EXECUTION PIPELINE
# ==========================================
if __name__ == "__main__":
    print("=== YouTube Shorts Automation Bot Started ===")

    script_text = generate_script()
    audio_path = generate_audio(script_text)
    image_url = generate_image_url()
    result = generate_hedra_video(audio_path, image_url)

    if result:
        print("\n=== Workflow Completed Successfully! ===")
    else:
        print("\n=== Workflow Failed at Video Generation Stage ===")
