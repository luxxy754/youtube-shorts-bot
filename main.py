import os
import json
import requests
from google import genai
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
ELEVEN_KEYS = [
    os.environ.get("ELEVEN_KEY_1"),
    os.environ.get("ELEVEN_KEY_2"),
    os.environ.get("ELEVEN_KEY_3")
]

def get_script_and_prompts():
    client = genai.Client(api_key=GEMINI_KEY)
    
    prompt = """
    Create a 15-second viral mind-blowing fact script for YouTube Shorts in HINDI (Hinglish script using Roman script).
    Also provide 3 extremely detailed, photorealistic visual image prompts in ENGLISH for AI image generator.
    
    Return ONLY a raw JSON object with keys:
    "script": "Hindi script under 25 words (e.g. Kya aap jante hain ki...)",
    "prompts": ["cinematic realistic photo of...", "detailed photographic image of...", "high quality 8k image of..."]
    Do not use markdown backticks.
    """
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    clean_json = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)

def generate_voiceover(text):
    # gTTS Hindi Fallback for 100% natural accent & zero API cost
    print("Generating Hindi Voiceover...")
    from gtts import gTTS
    tts = gTTS(text=text, lang='hi')
    tts.save("audio.mp3")
    return "audio.mp3"

def download_images(prompts):
    image_files = []
    for i, p in enumerate(prompts):
        # Adding quality modifiers to prompt
        detailed_prompt = f"{p}, cinematic lighting, photorealistic, 8k resolution, vertical 9:16 portrait"
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(detailed_prompt)}?width=1080&height=1920&nologo=true&model=flux"
        
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
    print("Hindi AI Short Rendered Successfully: final_short.mp4")

if __name__ == "__main__":
    data = get_script_and_prompts()
    print("Script Generated:", data["script"])
    audio_file = generate_voiceover(data["script"])
    images = download_images(data["prompts"])
    render_video(audio_file, images)
