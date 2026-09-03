import os
import re
import random
import requests
import subprocess
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont

# Gemini Setup
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

gemini_client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Warning: {e}")


def generate_viral_story():
    """Generates an engaging short story"""
    print("Generating Story via Gemini...")
    
    default_title = "Am I the wrong person for doing this?"
    default_body = "Yesterday my friend asked me for a favor that changed everything. I decided to stand my ground."

    if not gemini_client:
        return default_title, default_body

    prompt = (
        "Write a dramatic, short story for a YouTube Short (max 50 words).\n"
        "Return in EXACTLY this format:\n"
        "TITLE: [Catchy Title]\n"
        "STORY: [Short engaging story text]"
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

    card_w, card_h = 900, 400
    card_x = (width - card_w) // 2
    card_y = (height - card_h) // 2

    draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=25, fill=(255, 255, 255, 240))

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 40)
    except:
        font = ImageFont.load_default()

    words = title_text.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line + " " + word) < 25:
            current_line += " " + word
        else:
            lines.append(current_line.strip())
            current_line = word
    if current_line:
        lines.append(current_line.strip())

    y_text = card_y + 80
    for line in lines[:4]:
        draw.text((card_x + 50, y_text), line, fill=(0, 0, 0), font=font)
        y_text += 55

    card_path = "card.png"
    img.save(card_path)
    return card_path


def download_background_video():
    """Downloads Free HD Background Video"""
    print("Downloading Free Background Video...")
    video_urls = [
        "https://assets.mixkit.co/videos/preview/mixkit-abstract-fast-lines-of-light-31766-large.mp4",
        "https://assets.mixkit.co/videos/preview/mixkit-tunnel-of-futuristic-neon-lights-41552-large.mp4"
    ]
    url = random.choice(video_urls)
    bg_path = "bg_video.mp4"
    try:
        res = requests.get(url, timeout=30)
        if res.status_code == 200:
            with open(bg_path, "wb") as f:
                f.write(res.content)
            return bg_path
    except Exception as e:
        print(f"Background Download Error: {e}")

    # Fallback to creating a dark background if video fails
    print("Creating fallback dark background...")
    subprocess.run([
        "ffmpeg", "-f", "lavfi", "-i", "color=c=0x111122:s=1080x1920:d=60",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", bg_path
    ], check=True)
    return bg_path


def generate_free_audio(text):
    """Generates Free Voiceover using gTTS"""
    print("Generating Free Voiceover...")
    audio_path = "voice.mp3"
    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(audio_path)
    return audio_path


def build_final_short(bg_video, card_img, audio_file):
    """Combines Video, Image Card, and Voiceover via FFmpeg cleanly"""
    print("Rendering Final YouTube Short...")
    final_output = "final_short.mp4"

    ffmpeg_cmd = [
        "ffmpeg",
        "-i", bg_video,
        "-i", card_img,
        "-i", audio_file,
        "-filter_complex", "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[bg];[bg][1:v]overlay=0:0[v]",
        "-map", "[v]",
        "-map", "2:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-y",
        final_output
    ]

    subprocess.run(ffmpeg_cmd, check=True)
    return final_output


if __name__ == "__main__":
    print("=== Automated Free YouTube Shorts Bot Started ===")
    
    title, story = generate_viral_story()
    full_text = f"{title}. {story}"

    bg_video = download_background_video()
    card_img = create_card(title)
    audio_file = generate_free_audio(full_text)

    final_video = build_final_short(bg_video, card_img, audio_file)
    print(f"SUCCESS! Video Ready: {final_video}")
