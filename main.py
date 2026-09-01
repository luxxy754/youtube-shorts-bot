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
    """Gemini AI se Script generate karne ke liye with 503 Retry logic"""
    print("Generating Hindi Script...")
    if not client:
        return "हां भाई, चाय पी लो पहले, काम तो होता रहेगा!"

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    
    for model_name in models_to_try:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents="Write a very short, funny 1-line joke in Hindi (Devanagari script) for a YouTube Short character. Keep it under 15 words."
                )
                script_text = response.text.strip()
                print(f"Generated Script: {script_text}")
                return script_text
            except Exception as e:
                print(f"Gemini Error ({model_name}, Attempt {attempt+1}): {e}")
                time.sleep(3)
                
    print("All Gemini attempts failed. Using fallback script.")
    return "हां भाई, चाय पी लो पहले, काम तो होता रहेगा!"


def generate_audio(text, output_file="hindi_audio.mp3"):
    """gTTS ke zariye Audio File generate karne ke liye"""
    print("Generating Hindi Audio via gTTS...")
    tts = gTTS(text=text, lang="hi", slow=False)
    tts.save(output_file)
    print(f"Audio saved to: {output_file}")
    return output_file


def upload_audio_to_public_url(file_path):
    """Audio ko public URL me convert karne ke liye"""
    print("Uploading Audio to temporary public host...")
    try:
        with open(file_path, 'rb') as f:
            response = requests.post('https://tmpfiles.org/api/v1/upload', files={'file': f})
        
        if response.status_code == 200:
            data = response.json()
            url = data['data']['url'].replace('tmpfiles.org/', 'tmpfiles.org/dl/')
            print(f"Audio Hosted URL: {url}")
            return url
        else:
            print(f"Hosting Failed with code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Audio upload hosting error: {e}")
        return None


def generate_image_url():
    """Pollinations AI Character Image Link"""
    print("Generating 3D Character Image URL...")
    prompt = "3d Pixar style funny character, cute male character talking, front facing portrait, high quality"
    image_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=720&height=1280&nologo=true"
    print(f"Image URL: {image_url}")
    return image_url


def generate_hedra_video(audio_url, image_url):
    """Direct Hedra API flow handle karne ke liye"""
    print("\n--- Starting Hedra Video Generation ---")

    headers = {
        "X-API-Key": HEDRA_API_KEY,
        "Authorization": f"Bearer {HEDRA_API_KEY}",
        "Content-Type": "application/json"
    }

    endpoints = [
        "https://api.hedra.com/v1/characters",
        "https://api.hedra.com/v1/generations"
    ]
    
    payload = {
        "aspect_ratio": "9:16",
        "audio_url": audio_url,
        "image_url": image_url
    }

    gen_res = None
    for url in endpoints:
        print(f"Submitting job to endpoint: {url}")
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code in [200, 201]:
            gen_res = res
            break
        else:
            print(f"Endpoint {url} status: {res.status_code} -> {res.text}")

    if not gen_res:
        print("Hedra API submission failed completely.")
        return None

    job_data = gen_res.json()
    job_id = job_data.get("job_id") or job_data.get("id")
    print(f"Job Created Successfully! Job ID: {job_id}")

    # Status Polling
    status_endpoints = [
        f"https://api.hedra.com/v1/projects/{job_id}",
        f"https://api.hedra.com/v1/generations/{job_id}",
        f"https://api.hedra.com/v1/characters/{job_id}"
    ]
    
    max_retries = 36
    attempts = 0

    while attempts < max_retries:
        attempts += 1
        status_res = None
        
        for st_url in status_endpoints:
            res = requests.get(st_url, headers=headers)
            if res.status_code == 200:
                status_res = res
                break

        if status_res:
            res_json = status_res.json()
            job_status = res_json.get("status")

            if job_status in ["completed", "done", "succeeded"]:
                video_url = res_json.get("video_url") or res_json.get("url") or res_json.get("download_url")
                print(f"\nSUCCESS: Video URL: {video_url}")

                download_res = requests.get(video_url)
                if download_res.status_code == 200:
                    output_video = "final_short.mp4"
                    with open(output_video, "wb") as f:
                        f.write(download_res.content)
                    print(f"Saved locally as '{output_video}'")
                    return output_video
            elif job_status in ["failed", "error"]:
                print(f"Generation Failed with error: {res_json.get('error')}")
                return None

            print(f"Processing... status: '{job_status}' ({attempts}/{max_retries}). Waiting 5s.")
        else:
            print(f"Waiting for status update... ({attempts}/{max_retries})")
            
        time.sleep(5)

    print("Polling timed out!")
    return None


# ==========================================
# 3. MAIN EXECUTION PIPELINE
# ==========================================
if __name__ == "__main__":
    print("=== YouTube Shorts Automation Bot Started ===")

    script_text = generate_script()
    local_audio_path = generate_audio(script_text)
    
    public_audio_url = upload_audio_to_public_url(local_audio_path)
    if not public_audio_url:
        print("Failed to host audio. Terminating.")
        exit(1)

    image_url = generate_image_url()
    result = generate_hedra_video(public_audio_url, image_url)

    if result:
        print("\n=== Workflow Completed Successfully! ===")
    else:
        print("\n=== Workflow Failed ===")
