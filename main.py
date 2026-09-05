import os
import re
import sys
import time
import requests
import subprocess
from gtts import gTTS

try:
    from gradio_client import Client
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False

# Multiple Hugging Face Tokens setup for rotation & high limits
HF_TOKENS = [
    os.getenv("HF_TOKEN", ""),
    os.getenv("HF_TOKEN_2", ""),
    os.getenv("HF_TOKEN_3", ""),
]
HF_TOKENS = [t for t in HF_TOKENS if t.strip()]
HF_SPACE = os.getenv("HF_VIDEO_SPACES", "Wan-AI/Wan2.1")

def generate_animated_clip_hf(prompt_text, idx):
    """Generates a real AI video clip using Hugging Face Free Spaces with token rotation."""
    if not GRADIO_AVAILABLE:
        print("Gradio client not available.")
        return None

    tokens_to_try = HF_TOKENS if HF_TOKENS else [""]
    
    for token_idx, token in enumerate(tokens_to_try):
        for space_id in HF_SPACE.split(","):
            space_id = space_id.strip()
            try:
                print(f"Trying HF Space '{space_id}' using Token #{token_idx + 1}...")
                kwargs = {}
                if token:
                    kwargs["hf_token"] = token
                
                client = Client(space_id, **kwargs)
                
                # Predicting/Generating video from Space API
                result = client.predict(
                    prompt=prompt_text,
                    api_name="/generate"
                )
                
                if result and os.path.exists(str(result)):
                    output_file = f"scene_{idx}_hf.mp4"
                    os.rename(result, output_file)
                    print(f"Successfully generated video clip for scene {idx} using HF.")
                    return output_file
            except Exception as e:
                print(f"HF Space {space_id} with Token #{token_idx + 1} failed: {e}")
                continue
                
    print(f"Warning: Could not generate AI video for scene {idx} via HF. Falling back or skipping.")
    return None

# Baaki aapka main script ka logic yahan continue hoga...
if __name__ == "__main__":
    print("YouTube Shorts Bot with Multi-HF Token Support Initialized.")
