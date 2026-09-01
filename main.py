import os
import json
import time
import requests
from google import genai

# Configuration & Keys
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
    Create a funny 10-second viral Short script in HINDI (Roman script/Hinglish) spoken by a funny talking potato (Aalu) character.
    Also generate a detailed image prompt for the talking potato.
    
    Return ONLY a raw JSON object with keys:
    "script": "Hindi script under 20 words (e.g. Haan bhai, aalu hoon main...)",
    "image_prompt": "3d pixar style cute animated talking potato character, big expressive eyes, neutral mouth closed, funny face, 8k render, vertical portrait 9:16"
    Do not use markdown backticks.
    """
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    clean_json = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)

# 2. GENERATE AUDIO (gTTS)
def generate_audio(text):
    from gtts import gTTS
    tts = gTTS(text=text, lang='hi')
    audio_path = "audio.mp3"
    tts.save(audio_path)
    return audio_path

# 3. GENERATE CHARACTER IMAGE (POLLINATIONS FLUX)
def generate_character_image(prompt):
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=1080&height=1920&nologo=true&model=flux"
    res = requests.get(url)
    image_path = "character.jpg"
    with open(image_path, "wb") as f:
        f.write(res.content)
    return image_path

# 4. HEDRA LIP-SYNC ROTATOR (IMAGE + AUDIO -> TALKING VIDEO)
def create_hedra_talking_video(image_path, audio_path):
    for idx, key in enumerate(HEDRA_KEYS):
        if not key:
            continue
        print(f"Trying Hedra Key {idx + 1}...")
        headers = {"X-API-KEY": key}
        
        try:
            # Step A: Upload Assets
            with open(image_path, "rb") as img_f, open(audio_path, "rb") as aud_f:
                init_res = requests.post(
                    "https://api.hedra.com/v1/characters",
                    headers=headers,
                    files={"image": img_f, "audio": aud_f}
                )
            if init_res.status_code != 200:
                print(f"Key {idx + 1} failed or limit reached. Status: {init_res.status_code}")
                continue
                
            job_data = init_res.json()
            job_id = job_data.get("job_id") or job_data.get("id")
            
            # Step B: Poll Status
            print("Processing video animation...")
            while True:
                status_res = requests.get(f"https://api.hedra.com/v1/jobs/{job_id}", headers=headers)
                status_data = status_res.json()
                status = status_data.get("status")
                
                if status == "completed":
                    video_url = status_data.get("video_url")
                    video_res = requests.get(video_url)
                    with open("final_short.mp4", "wb") as vf:
                        vf.write(video_res.content)
                    print("Talking Aalu Video Generated Successfully!")
                    return "final_short.mp4"
                elif status == "failed":
                    print("Hedra rendering failed, trying next key...")
                    break
                
                time.sleep(5)
        except Exception as e:
            print(f"Error with key {idx + 1}: {e}")
            
    print("All Hedra Keys failed or expired!")
    return None

if __name__ == "__main__":
    data = get_script_and_prompt()
    print("Script:", data["script"])
    
    audio_file = generate_audio(data["script"])
    image_file = generate_character_image(data["image_prompt"])
    
    video_file = create_hedra_talking_video(image_file, audio_file)
