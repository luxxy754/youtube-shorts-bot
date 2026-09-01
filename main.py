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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")

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
    """Gemini AI se Script generate karne ke liye"""
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
                time.sleep(2)
                
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


def generate_lipsync_video(audio_url, image_url):
    """Replicate API / SadTalker backend for Lip-Sync Video"""
    print("\n--- Starting Video Generation ---")

    if not REPLICATE_API_TOKEN:
        print("REPLICATE_API_TOKEN missing. Direct video output fallback activated.")
        # Direct MP4 fallback download
        download_res = requests.get(image_url)
        if download_res.status_code == 200:
            print("Image generated successfully as asset.")
            return None

    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    url = "https://api.replicate.com/v1/predictions"
    payload = {
        "version": "c52892e22f2549d49931b2e65d83648a39a73752e259e000c25b822d6b38c032",
        "input": {
            "source_image": image_url,
            "driven_audio": audio_url,
            "still": True,
            "enhancer": "gfpgan"
        }
    }

    print("Submitting LipSync job to Replicate API...")
    res = requests.post(url, json=payload, headers=headers)
    
    if res.status_code not in [200, 201]:
        print(f"Replicate Submission Error {res.status_code}: {res.text}")
        return None

    prediction = res.json()
    prediction_id = prediction.get("id")
    print(f"Prediction Created. ID: {prediction_id}")

    status_url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
    max_retries = 36
    attempts = 0

    while attempts < max_retries:
        attempts += 1
        st_res = requests.get(status_url, headers=headers)
        
        if st_res.status_code == 200:
            data = st_res.json()
            status = data.get("status")

            if status == "succeeded":
                video_url = data.get("output")
                print(f"\nSUCCESS: Video URL: {video_url}")

                download_res = requests.get(video_url)
                if download_res.status_code == 200:
                    output_video = "final_short.mp4"
                    with open(output_video, "wb") as f:
                        f.write(download_res.content)
                    print(f"Saved locally as '{output_video}'")
                    return output_video
            elif status == "failed":
                print(f"Generation Failed: {data.get('error')}")
                return None

            print(f"Status: '{status}' ({attempts}/{max_retries}). Waiting 5s...")
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
    result = generate_lipsync_video(public_audio_url, image_url)

    if result:
        print("\n=== Workflow Completed Successfully! ===")
    else:
        print("\n=== Workflow Failed ===")
