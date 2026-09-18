import asyncio
import os
import edge_tts

VOICE = "hi-IN-SwaraNeural"
RATE = "-5%"
PITCH = "-4Hz"

async def generate_audio(text, output_path):
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH)
    await communicate.save(output_path)

def main():
    print("Synthesizing voiceover with Edge-TTS...")
    os.makedirs("output", exist_ok=True)
    
    script_path = "output/script.txt"
    if os.path.exists(script_path):
        with open(script_path, "r", encoding="utf-8") as f:
            script_text = f.read().strip()
    else:
        script_text = "Dosto, AI ki duniya mein naye trends aa rahe hain!"

    audio_path = "output/voiceover.mp3"
    asyncio.run(generate_audio(script_text, audio_path))
    print(f"Voiceover saved to {audio_path}")

if __name__ == "__main__":
    main()
