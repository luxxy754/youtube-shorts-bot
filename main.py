import os
import asyncio
import requests
import replicate
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip

# 1. Replicate API se Image/Animation Generate Karna
def generate_ai_image(prompt):
    print("Generating AI visual using Replicate...")
    # Flux Schnell Model (Fast & High Quality)
    output = replicate.run(
        "black-forest-labs/flux-schnell",
        input={
            "prompt": prompt,
            "aspect_ratio": "9:16", # YouTube Shorts / Reels Format
            "output_format": "webp"
        }
    )
    
    # Image download karke local file me save karein
    image_url = str(output[0])
    img_data = requests.get(image_url).content
    image_path = "scene.jpg"
    with open(image_path, "wb") as handler:
        handler.write(img_data)
    print("Image saved successfully!")
    return image_path

# 2. Edge-TTS se Audio Generate Karna
async def generate_voiceover(text, output_audio):
    print("Generating voiceover...")
    voice = "hi-IN-SwaraNeural"  # Hindi voice
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_audio)
    print("Audio saved successfully!")

# 3. Audio aur Image ko Combine Karke Video Banana
def build_short_video(image_path, audio_path, output_video):
    print("Rendering final video...")
    audio_clip = AudioFileClip(audio_path)
    
    # Image clip ki duration audio jitni rakhein
    image_clip = ImageClip(image_path).set_duration(audio_clip.duration)
    
    # Audio add karein
    video_clip = image_clip.set_audio(audio_clip)
    
    # Video render karein
    video_clip.write_videofile(
        output_video,
        fps=24,
        codec="libx264",
        audio_codec="aac"
    )
    print(f"Video completely built: {output_video}")

# Pipeline Execution
if __name__ == "__main__":
    script_text = "Dosto, yeh ek AI dwara banaya gaya automated short video hai."
    image_prompt = "A futuristic cyberpunk city with glowing neon lights, 8k resolution, cinematic lighting"
    
    audio_file = "voice.mp3"
    final_output = "generated_short.mp4"

    # Step A: Image Generate Karein
    img_file = generate_ai_image(image_prompt)
    
    # Step B: Audio Generate Karein
    asyncio.run(generate_voiceover(script_text, audio_file))
    
    # Step C: Merge Karein
    build_short_video(img_file, audio_file, final_output)
