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
    "image_prompt": "3d pixar style cute animated talking potato character, big expressive eyes, neutral closed mouth, funny face, 8k render, vertical portrait 9:16"
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
            
        print(f"Trying Hedra Key {idx + 1}...")
        headers = {"X-API-KEY": key.strip()}
        
        try:
            # 1. Upload Audio
            with open(audio_path, "rb") as aud_f:
                audio_res = requests.post(
                    "https://api.hedra.com/v1/audio",
                    headers=headers,
                    files={"file": aud_f}
                )
            if audio_res.status_code != 200:
                print(f"Audio upload failed with key {idx + 1}. Code: {audio_res.status_code}, Resp: {audio_res.text}")
                continue
            audio_url = audio_res.json().get("url")

            # 2. Upload Image
            with open(image_path, "rb") as img_f:
                img_res = requests.post(
                    "https://api.hedra.com/v1/image",
                    headers=headers,
                    files={"file": img_f}
                )
            if img_res.status_code != 200:
                print(f"Image upload failed with key {idx + 1}. Code: {img_res.status_code}, Resp: {img_res.text}")
                continue
            image_url = img_res.json().get("url")

            # 3. Generate Project
            payload = {
                "aspectRatio": "9:16",
                "audioUrl": audio_url,
                "imageUrl": image_url
            }
            gen_res = requests.post(
                "https://api.hedra.com/v1/characters",
                headers=headers,
                json=payload
            )
            
            if gen_res.status_code not in [200, 201]:
                print(f"Character job failed with key {idx + 1}. Code: {gen_res.status_code}, Resp: {gen_res.text}")
                continue

            job_id = gen_res.json().get("jobId") or gen_res.json().get("id")
            print(f"Job created successfully! Job ID: {job_id}")

            # 4. Poll Status
            print("Rendering lip-sync video animation...")
            for _ in range(30):  # max ~2.5 mins wait
                status_res = requests.get(f"https://api.hedra.com/v1/projects/{job_id}", headers=headers)
                status_data = status_res.json()
                status = status_data.get("status")
                
                if status == "completed":
                    video_url = status_data.get("videoUrl") or status_data.get("video_url")
                    video_res = requests.get(video_url)
                    with open("final_short.mp4", "wb") as vf:
                        vf.write(video_res.content)
                    print("Talking Animated Video Generated Successfully!")
                    return "final_short.mp4"
                elif status in ["failed", "error"]:
                    print(f"Hedra job status failed: {status_data}")
                    break
                
                time.sleep(5)
        except Exception as e:
            print(f"Error with key {idx + 1}: {e}")
            
    print("All Hedra Keys failed or expired!")
    return None

if __name__ == "__main__":
    data = get_script_and_prompt()
    print("Generated Script:", data["script"])
    
    audio_file = generate_audio(data["script"])
    image_file = generate_character_image(data["image_prompt"])
    video_file = create_hedra_talking_video(image_file, audio_file)
