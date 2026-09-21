import os
import asyncio
import requests
import replicate
import edge_tts
from moviepy.editor import VideoFileClip, AudioFileClip

# 1. Replicate API se Moving 3D Animation Video Generate Karna
def generate_ai_animation(prompt):
    print("Generating 3D Animation Video clip using Replicate MiniMax...")
    
    # MiniMax Video Generation Model
    output = replicate.run(
        "minimax/video-01",
        input={
            "prompt": prompt,
            "prompt_optimizer": True
        }
    )
    
    # Video clip download karke local file me save karein
    video_url = str(output)
    video_data = requests.get(video_url).content
    clip_path = "scene_animation.mp4"
    
    with open(clip_path, "wb") as handler:
        handler.write(video_data)
        
    print("Animation clip downloaded successfully!")
    return clip_path

# 2. Edge-TTS se Voiceover Generate Karna
async def generate_voiceover(text, output_audio):
    print("Generating voiceover with Edge-TTS...")
    voice = "hi-IN-SwaraNeural"  # Hindi Voice
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_audio)
    print("Audio saved successfully!")

# 3. Animated Video Clip aur Audio ko Merge Karna
def build_short_video(video_clip_path, audio_path, output_video):
    print("Merging animation and audio...")
    
    video_clip = VideoFileClip(video_clip_path)
    audio_clip = AudioFileClip(audio_path)
    
    # Agar video audio se lambi hai toh cut kar dein, agar chhoti hai toh loop karein
    if video_clip.duration < audio_clip.duration:
        # Audio ki length ke hisab se loop
        loops = int(audio_clip.duration / video_clip.duration) + 1
        final_video = video_clip.loop(n=loops).subclip(0, audio_clip.duration)
    else:
        final_video = video_clip.subclip(0, audio_clip.duration)
    
    # Audio clip apply karein
    final_video = final_video.set_audio(audio_clip)
    
    # Final Short render karein
    final_video.write_videofile(
        output_video,
        fps=24,
        codec="libx264",
        audio_codec="aac"
    )
    print(f"Final 3D Short ready: {output_video}")

# Execution Flow
if __name__ == "__main__":
    # Aapka script/dialogue
    script_text = "Kabhi kisi billi par bharosa mat karna, yeh bohot chalak hoti hain!"
    
    # 3D Animation Prompt (Pixar/3D style animated short ke liye)
    animation_prompt = "3D Pixar style funny cute cat wearing a helmet driving a small motorcycle, animated moving scene, 8k resolution, cinematic lighting"
    
    audio_file = "voiceover.mp3"
    final_output = "generated_short.mp4"

    # Step 1: 3D Animation Video Generate Karein
    anim_clip = generate_ai_animation(animation_prompt)
    
    # Step 2: Edge-TTS Voiceover Generate Karein
    asyncio.run(generate_voiceover(script_text, audio_file))
    
    # Step 3: Combine aur Render Karein
    build_short_video(anim_clip, audio_file, final_output)
