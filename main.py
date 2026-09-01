import os
import json
import time
import requests
from google import genai

# Configuration & Keys from GitHub Secrets
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
HEDRA_KEYS = [
    os.environ.get("HEDRA_KEY_1"),
    os.environ.get("HEDRA_KEY_2"),
    os.environ.get("HEDRA_KEY_3")
]

# 1. GENERATE HINDI SCRIPT & CHARACTER PROMPT
def get_script_and_prompt():
    client = genai.Client(api_key=GEMINI_KEY)
    prompt = """
    Create a funny 10-second viral Short script in HINDI (Roman script/Hinglish). 
    The speaker should be a RANDOM funny 3D character (e.g. Potato, Tomato, Onion, Burger, Apple, or Coffee Cup). 
    Pick a DIFFERENT character and topic every time.
    
    Return ONLY a raw JSON object with keys:
    "script": "Funny Hindi script under 20 words (e.g. Haan bhai, main aalu hoon...)",
    "image_prompt": "3d pixar style cute animated talking character, big expressive eyes, neutral closed mouth, funny face, 8k render, vertical portrait 9:16"
    Do not use markdown backticks.
    """
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    clean_json = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)

# 2. GENERATE HINDI AUDIO (gTTS)
def generate_audio(text):
    print("Generating Hindi Audio...")
    from gtts import gTTS
    tts = gTTS(text=text, lang='hi')
    audio_path = "audio.mp3"
    tts.save(audio_path)
    return audio_path

# 3. GENERATE CHARACTER IMAGE (POLLINATIONS FLUX)
def generate_character_image(prompt):
    print("Generating 3D Character Image...")
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=1080&height=1920&nologo=true&model=flux"
    res = requests.get(url)
    image_path = "character.jpg"
    with open(image_path, "wb") as f:
        f.write(res.content)
    return image_path

# 4. HEDRA LIP-SYNC ROTATOR (FIXED API REQUEST HANDLING)
def create_hedra_talking_video(image_path, audio_path):
    for idx, key in enumerate(HEDRA_KEYS):
        if not key or not key.strip():
            print(f"Hedra Key {idx + 1} missing, skipping...")
            continue
            
        print(f"Trying Hedra Key {idx + 1}...")
        headers = {"X-API-KEY": key.strip()}
        
        try:
            with open(image_path, "rb") as img_f, open(audio_path, "rb") as aud_f:
                files = {
                    "image": ("character.jpg", img_f, "image/jpeg"),
                    "audio": ("audio.mp3", aud_f, "audio/mpeg")
                }
                res = requests.post(
                    "https://api.hedra.com/v1/characters",
                    headers=headers,
                    files=files
                )
            
            print(f"Key {idx + 1} Request Status Code: {res.status_code}")
            print(f"Response Body: {res.text}")

            if res.status_code not in [200, 201]:
                print(f"Key {idx + 1} request rejected. Trying next key...")
                continue

            job_data = res.json()
            job_id = job_data.get("job_id") or job_data.get("id") or job_data.get("jobId")
            
            if not job_id:
                print("Job ID missing from response, trying next key...")
                continue

            print(f"Hedra Job Started! Job ID: {job_id}")

            # Polling Job Status (Wait up to 3 minutes)
            for _ in range(36):
                status_res = requests.get(f"https://api.hedra.com/v1/jobs/{job_id}", headers=headers)
                if status_res.status_code != 200:
                    status_res = requests.get(f"https://api.hedra.com/v1/characters/{job_id}", headers=headers)
                
                status_data = status_res.json()
                status = status_data.get("status")
                print(f"Current Video Status: {status}")
                
                if status in ["completed", "complete", "done"]:
                    video_url = status_data.get("video_url") or status_data.get("videoUrl") or status_data.get("url")
                    video_res = requests.get(video_url)
                    with open("final_short.mp4", "wb") as vf:
                        vf.write(video_res.content)
                    print("Talking Video Generated & Saved as final_short.mp4!")
                    return "final_short.mp4"
                elif status in ["failed", "error"]:
                    print("Hedra rendering failed on server side.")
                    break
                
                time.sleep(5)

        except Exception as e:
            print(f"Error executing key {idx + 1}: {e}")
            
    print("All Hedra Keys failed!")
    return None

if __name__ == "__main__":
    data = get_script_and_prompt()
    print("Generated Script:", data["script"])
    
    audio_file = generate_audio(data["script"])
    image_file = generate_character_image(data["image_prompt"])
    video_file = create_hedra_talking_video(image_file, audio_file)
