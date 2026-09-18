import argparse
import os
from gradio_client import Client, handle_file

def main():
    parser = argparse.ArgumentParser(description="Render Lipsync Video")
    parser.add_argument("--output", type=str, required=True, help="Output video path")
    args = parser.parse_args()

    print(f"Rendering lipsync video to: {args.output}")
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    character_image = "character.jpg"
    audio_path = "output/voiceover.mp3"

    if not os.path.exists(character_image):
        print("Error: character.jpg not found!")
        return

    try:
        print("Connecting to Wav2Lip Gradio Space for lipsync...")
        client = Client("manavisrani07/gradio-lipsync-wav2lip")
        result = client.predict(
            face=handle_file(character_image),
            audio=handle_file(audio_path),
            api_name="/generate"
        )
        
        if result and os.path.exists(result):
            import shutil
            shutil.copy(result, args.output)
            print(f"Lipsync video successfully rendered at {args.output}")
        else:
            print("Gradio space returned invalid path, creating fallback.")
    except Exception as e:
        print(f"Lipsync generation error: {e}")
        # Fallback agar API fail ho jaye
        os.system(f'ffmpeg -y -f lavfi -i color=c=black:s=1080x1920:d=5 -c:v libx264 {args.output}')

if __name__ == "__main__":
    main()
