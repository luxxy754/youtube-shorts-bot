import argparse
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    image = root / "character.jpg"
    audio = root / "output" / "voiceover.mp3"
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    if not image.exists():
        raise FileNotFoundError(image)
    if not audio.exists():
        raise FileNotFoundError(audio)

    # Reliable no-GPU fallback. A remote lipsync service is optional and is not
    # required for the YouTube pipeline to complete.
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(image), "-i", str(audio),
        "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest",
        "-movflags", "+faststart", str(output)
    ], check=True)

    print(f"Video rendered: {output}")


if __name__ == "__main__":
    main()
