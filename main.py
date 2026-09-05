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

# Hugging Face Tokens setup (GitHub secrets se uthayega)
HF_TOKENS = [
    os.getenv("HF_TOKEN", ""),
    os.getenv("HF_TOKEN_2", ""),
    os.getenv("HF_TOKEN_3", ""),
    os.getenv("HF_TOKEN_4", ""),
]
HF_TOKENS = [t for t in HF_TOKENS if t.strip()]
HF_SPACE = os.getenv("HF_VIDEO_SPACES", "Wan-AI/Wan2.1")

def generate_animated_clip_hf(prompt_text, idx):
    """Generates a real AI video clip using Hugging Face Free Spaces (e.g., Wan2.1)."""
    if not GRADIO_AVAILABLE:
        print("Gradio client not available.")
        return None

    # Tokens ko rotate karne ke liye logic
    tokens_to_try = HF_TOKENS if HF_TOKENS else [""]
    
    for token in tokens_to_try:
        for space_id in HF_SPACE.split(","):
            space_id = space_id.strip()
            try:
                print(f"Trying HF Space '{space_id}' with token available: {bool(token)}...")
                kwargs = {}
                if token:
                    kwargs["hf_token"] = token
                
                client = Client(space_id, **kwargs)
                
                # Wan2.1 ya standard video generation spaces ke parameters
                result = client.predict(
                    prompt=prompt_text,
                    api_name="/generate" # Space ke mutabiq endpoint change ho sakta hai
                )
                
                # Resulting video path
                if result and os.path.exists(str(result)):
                    output_file = f"scene_{idx}_hf.mp4"
                    os.rename(result, output_file)
                    return output_file
            except Exception as e:
                print(f"HF Space {space_id} failed: {e}")
                continue
                
    return None
