import argparse
import os
from subprocess import call

def main():
    parser = argparse.ArgumentParser(description="Render Video")
    parser.add_argument("--output", type=str, required=True, help="Output video path")
    args = parser.parse_args()

    print(f"Rendering video to: {args.output}")
    
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # FFmpeg se ek 5-second ki sample video render karna
    cmd = f'ffmpeg -y -f lavfi -i color=c=black:s=1080x1920:d=5 -vf "drawtext=text=\'AI Short Output\':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2" {args.output}'
    os.system(cmd)

if __name__ == "__main__":
    main()
