import os
import re
import random
import requests
import subprocess
from PIL import Image, ImageDraw, ImageFont

# Gemini Setup
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ELEVEN_KEY = os.getenv("ELEVEN_KEY_1") or os.getenv("ELEVEN_KEY_2") or ""

gemini_client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Warning: {e}")


def generate_hinglish_viral_story():
    """Generates a conversational Hinglish story like a real human talking"""
    print("Generating Conversational Hinglish Story via Gemini...")
    
    default_title = "Bhai Ek Bohot Ajeeb Baat Hui"
    default_body = "Kal raat ko mera dost mujhe call karke bolta hai ki uske ghar ke bahar koi khada hai. Jab main wahan pohncha to scene hi kuch aur tha!"

    if not gemini_client:
        return default_title, default_body

    prompt = (
        "Write a 100% natural, casual Hindi/Hinglish story for a YouTube Short (Roman Script - Hinglish).\n"
        "It should sound like a young male friend talking directly to the audience in a catchy way.\n"
        "Strictly Max 40 words.\n\n"
        "Return EXACTLY in this format:\n"
        "TITLE: [Catchy Hinglish Title]\n"
        "STORY: [Natural Hinglish Story Text]"
    )

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        raw_text = response.text.strip()
        
        title_match = re.search(r'TITLE:\s*(.*)', raw_text)
        story_match = re.search(r'STORY:\s*(.*)', raw_text)

        title = title_match.group(1).strip() if title_match else default_title
        body = story_match.group(1).strip() if story_match else default_body
        return title, body
    except Exception as e:
        print(f"Gemini Story Error: {e}")
        return default_title, default_body


def create_card(title_text):
    """Generates Text Card Overlay Image"""
    width, height = 1080, 1920
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    card_w, card_h = 920, 380
    card_x = (width - card_w) // 2
    card_y = (height - card_h) // 2

    draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=30, fill=(255, 255, 255, 245))

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 42)
    except:
        font = ImageFont.load_default()

    words = title_text.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line + " " + word) < 22:
            current_line += " " + word
        else:
            lines.append(current_line.strip())
            current_line = word
    if current_line:
        lines.append(current_line.strip())

    y_text = card_y + 70
    for line in lines[:4]:
        draw.text((card_x + 40, y_text), line, fill=(15, 15, 15), font=font)
        y_text += 60

    card_path = "card.png"
    img.save(card_path)
    return card_path


def download_guaranteed_moving_background():
    """Downloads guaranteed high quality vertical motion video"""
    print("Downloading High Quality Moving Background Video...")
    bg_urls = [
        "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
        "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
        "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4"
    ]
    url = random.choice(bg_urls)
    bg_path = "bg_video.mp4"

    try:
        res = requests.get(url, stream=True, timeout=30)
        if res.status_code == 200:
            with open(bg_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=1024*1024):
                    f.write(chunk)
            print("Background Video Downloaded Successfully!")
            return bg_path
    except Exception as e:
        print(f"Video Download Error: {e}")

    # FFmpeg dynamic motion background fallback (Neon Moving Gradient)
    print("Generating Dynamic Moving Motion Background via FFmpeg...")
    subprocess.run([
        "ffmpeg", "-f", "lavfi",
        "-i", "testsrc=size=1080x1920:rate=30",
        "-t", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", bg_path
    ], check=True)
    return bg_path


def generate_realistic_elevenlabs_voice(text):
    """Uses ElevenLabs Realistic Male Voice (Adam Voice)"""
    print("Generating Ultra Realistic Male Voice via ElevenLabs...")
    audio_path = "voice.mp3"

    # Deep Realistic Male Voice ID (Adam)
    voice_id = "pNInz6obpgDQGcFmaJgB"

    if ELEVEN_KEY:
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            headers = {
                "xi-api-key": ELEVEN_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.35,
                    "similarity_boost": 0.85,
                    "style": 0.20,
                    "use_speaker_boost": True
                }
            }
            res = requests.post(url, json=payload, headers=headers, timeout=25)
            if res.status_code == 200:
                with open(audio_path, "wb") as f:
                    f.write(res.content)
                print("Realistic ElevenLabs Voiceover Generated!")
                return audio_path
            else:
                print(f"ElevenLabs API Error Code: {res.status_code}, Response: {res.text}")
        except Exception as e:
            print(f"ElevenLabs Exception: {e}")

    # Fallback gTTS if Key fails
    from gtts import gTTS
    print("Fallback to gTTS Audio...")
    tts = gTTS(text=text, lang="hi", slow=False)
    tts.save(audio_path)
    return audio_path


def build_final_short(bg_video, card_img, audio_file):
    """Combines Video, Image Card, and Voiceover using robust FFmpeg settings"""
    print("Rendering Final YouTube Short...")
    final_output = "final_short.mp4"

    ffmpeg_cmd = [
        "ffmpeg",
        "-stream_loop", "-1", "-i", bg_video,
        "-i", card_img,
        "-i", audio_file,
        "-filter_complex", "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[bg];[bg][1:v]overlay=0:0[v]",
        "-map", "[v]",
        "-map", "2:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-y",
        final_output
    ]

    subprocess.run(ffmpeg_cmd, check=True)
    return final_output


if __name__ == "__main__":
    print("=== Automated Real-Human Voice Hinglish Short Bot Started ===")
    
    title, story = generate_hinglish_viral_story()
    full_text = f"{title}. {story}"

    bg_video = download_guaranteed_moving_background()
    card_img = create_card(title)
    audio_file = generate_realistic_elevenlabs_voice(full_text)

    final_video = build_final_short(bg_video, card_img, audio_file)
    print(f"SUCCESS! Video Ready: {final_video}")
