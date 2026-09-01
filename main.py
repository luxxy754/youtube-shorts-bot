import os
import json
import time
import requests
from google import genai

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
HEDRA_KEYS = [
    os.environ.get("HEDRA_KEY_1"),
    os.environ.get("HEDRA_KEY_2"),
    os.environ.get("HEDRA_KEY_3")
]

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

def generate_audio(text):
    print("Generating Hindi Audio...")
    from gtts import gTTS
    tts = gTTS(text=text, lang='hi')
    audio_path = "audio.mp3"
    tts.save(audio_path)
    return audio_path

def generate_character_image(prompt):
    print("Generating 3D Character Image...")
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=1080&height=1920&nologo=true&model=flux"
    res = requests.get(url)
    image_path = "character.jpg"
    with open(image_path, "wb") as f:
        f.write(res.content)
    return image_path

def create_hedra_talking_video(image_path, audio_path):
    for idx, key in enumerate(HEDRA_KEYS):
        if not key or not key.strip():
            print(f"Hedra Key {idx + 1} missing, skipping...")
            continue
            
        print(f"Trying Hedra V3 Key {idx + 1}...")
        headers = {
            "X-API-KEY": key.strip(),
            "Authorization": f"Bearer {key.strip()}"
        }
        
        try:
            # 1. Upload Audio
            print("Uploading Audio...")
            with open(audio_path, "rb") as af:
                res_aud = requests.post("https://api.hedra.com/v1/audio", headers=headers, files={"file": af})
            if res_aud.status_code not in [200, 201]:
                # Try v2 asset endpoint if v1 fails
                with open(audio_path, "rb") as af:
                    res_aud = requests.post("https://api.hedra.com/v2/assets", headers=headers, files={"file": af})
            
            audio_url = res_aud.json().get("url") or res_aud.json().get("asset_url")

            # 2. Upload Image
            print("Uploading Image...")
            with open(image_path, "rb") as imgf:
                res_img = requests.post("https://api.hedra.com/v1/image", headers=headers, files={"file": imgf})
            if res_img.status_code not in [200, 201]:
                with open(image_path, "rb") as imgf:
                    res_img = requests.post("https://api.hedra.com/v2/assets", headers=headers, files={"file": imgf})
            
            image_url = res_img.json().get("url") or res_img.json().get("asset_url")

            # 3. Generate Project
            print("Submitting Generation Job...")
            payload = {
                "aspectRatio": "9:16",
                "audioUrl": audio_url,
                "imageUrl": image_url
            }
            res_gen = requests.post("https://api.hedra.com/v1/characters", headers=headers, json=payload)
            if res_gen.status_code not in [200, 201]:
                res_gen = requests.post("https://api.hedra.com/v2/generations", headers=headers, json=payload)

            print(f"Gen Response Code: {res_gen.status_code}")
            if res_gen.status_code not in [200, 201]:
                print(f"Key {idx + 1} rejected. Response: {res_gen.text}")
                continue

            job_id = res_gen.json().get("id") or res_gen.json().get("job_id") or res_gen.json().get("jobId")
            print(f"Hedra Job Started! Job ID: {job_id}")

            # 4. Polling Status
            print("Rendering Video...")
            for _ in range(36):
                status_res = requests.get(f"https://api.hedra.com/v1/projects/{job_id}", headers=headers)
                if status_res.status_code != 200:
                    status_res = requests.get(f"https://api.hedra.com/v2/generations/{job_id}", headers=headers)
                
                status_data = status_res.json()
                status = status_data.get("status")
                print(f"Status: {status}")
                
                if status in ["completed", "complete"]:
                    video_url = status_data.get("videoUrl") or status_data.get("video_url") or status_data.get("url")
                    video_res = requests.get(video_url)
                    with open("final_short.mp4", "wb") as vf:
                        vf.write(video_res.content)
                    print("Talking Video Generated & Saved as final_short.mp4!")
                    return "final_short.mp4"
                elif status in ["failed", "error"]:
                    print(f"Rendering failed: {status_data}")
                    break
                
                time.sleep(5)

        except Exception as e:
            print(f"Error with Key {idx + 1}: {e}")
            
    print("All Hedra Keys failed!")
    return None

if __name__ == "__main__":
    data = get_script_and_prompt()
    print("Script:", data["script"])
    
    audio_file = generate_audio(data["script"])
    image_file = generate_character_image(data["image_prompt"])
    video_file = create_hedra_talking_video(image_file, audio_file)
