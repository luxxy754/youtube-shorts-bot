import os
import json
import requests
import google.generativeai as genai
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

# Keys from GitHub Secrets
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
ELEVEN_KEYS = [
    os.environ.get("ELEVEN_KEY_1"),
    os.environ.get("ELEVEN_KEY_2"),
    os.environ.get("ELEVEN_KEY_3")
]

def get_script_and_prompts():
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = """
    Create a 15-second interesting mind-blowing short fact script.
    Return ONLY a raw JSON object with keys:
    "script": "short voiceover text under 25 words",
    "prompts": ["image prompt 1", "image prompt 2", "image prompt 3"]
    Do not use markdown backticks.
    """
    response = model.generate_content(prompt)
    clean_json = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)

def generate_voiceover(text):
    voice_id = "21m00Tcm4TlvDq8ikWAM" # Default voice
    for key in ELEVEN_KEYS:
        if not key:
            continue
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": key}
        payload = {"text": text, "model_id": "eleven_monolingual_v1"}
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code == 200:
            with open("audio.mp3", "wb") as f:
                f.write(res.content)
            print("Audio created successfully!")
            return "audio.mp3"
    
    print("ElevenLabs failed. Falling back to gTTS...")
    from gtts import gTTS
    tts = gTTS(text=text, lang='en')
    tts.save("audio.mp3")
    return "audio.mp3"

def download_images(prompts):
    image_files = []
    for i, p in enumerate(prompts):
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(p)}?width=1080&height=1920&nologo=true"
        res = requests.get(url)
        filename = f"img_{i}.jpg"
        with open(filename, "wb") as f:
            f.write(res.content)
        image_files.append(filename)
    return image_files

def render_video(audio_path, image_paths):
    audio = AudioFileClip(audio_path)
    duration_per_img = audio.duration / len(image_paths)
    
    clips = []
    for img in image_paths:
        clip = ImageClip(img).set_duration(duration_per_img)
        clips.append(clip)
        
    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)
    video.write_videofile("final_short.mp4", fps=24, codec="libx264")
    print("Video Rendered Successfully: final_short.mp4")

if __name__ == "__main__":
    data = get_script_and_prompts()
    audio_file = generate_voiceover(data["script"])
    images = download_images(data["prompts"])
    render_video(audio_file, images)
