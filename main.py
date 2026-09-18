import asyncio
import edge_tts
import json
import os
import requests
import sys
import time
import traceback

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False

try:
    from gradio_client import Client as GradioClient
    try:
        from gradio_client import handle_file
    except ImportError:
        def handle_file(path):
            return path
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False

try:
    from huggingface_hub import snapshot_download
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False

# ==================== CONFIGURATION ====================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# --- TTS Configuration ---
# hi-IN-SwaraNeural ek natural, expressive female voice hai jo Hindi/Urdu + English
# mix ko achay se handle karti hai. Rate/pitch ko neutral rakha hai (-5%/-4Hz pehle
# usse thoda slow/flat + "ruk ruk kar" wala effect aata tha).
VOICE = os.getenv("EDGE_TTS_VOICE", "hi-IN-SwaraNeural")
RATE = os.getenv("EDGE_TTS_RATE", "+2%")
PITCH = os.getenv("EDGE_TTS_PITCH", "+1Hz")
OUTPUT_AUDIO_FILE = "voiceover.mp3"

HF_KEYS = [
    os.getenv("HF_TOKEN", ""),
    os.getenv("HF_TOKEN_2", ""),
    os.getenv("HF_TOKEN_3", ""),
]

DEFAULT_LIPSYNC_SPACES = "manavisrani07/gradio-lipsync-wav2lip,Artificial-superintelligence/gradio-lipsync-wav2lip"
LIPSYNC_SPACES = [s.strip() for s in os.getenv("LIPSYNC_SPACES", DEFAULT_LIPSYNC_SPACES).split(",") if s.strip()]
LIPSYNC_CHECKPOINT = os.getenv("LIPSYNC_CHECKPOINT", "wav2lip")  
LIPSYNC_TIMEOUT_SECONDS = int(os.getenv("LIPSYNC_TIMEOUT_SECONDS", "420"))
# Public HF Spaces baar baar sleep/pause ho jati hain. Agar pehle round mein sab
# fail ho jayein, to thoda wait karke poori list dobara try karo (kuch der mein
# wapas online aa sakti hain).
LIPSYNC_RETRY_ROUNDS = int(os.getenv("LIPSYNC_RETRY_ROUNDS", "3"))
LIPSYNC_ROUND_WAIT_SECONDS = int(os.getenv("LIPSYNC_ROUND_WAIT_SECONDS", "45"))

CHARACTER_IMAGE = "character.jpg"
OUTPUT_VIDEO_PATH = "output/short_video.mp4"

print("AI Influencer Bot Initialized with Edge-TTS.")


def generate_influencer_script():
    fallback_title = "Aaj Ki Viral Baat! #Shorts"
    fallback_script = (
        "Guys, ek cheez batao aajkal AI itni fast chal rahi hai na ke sach mein mazaa aa raha hai. "
        "Matlab jahan dekho wahan koi na koi naya tool aa raha hai jo life easy bana raha hai, "
        "chahe wo study ho, business ho ya bas apna daily kaam. Best part ye hai ke ye sab "
        "seekhna itna mushkil bhi nahi, bas thoda curious rehna padta hai aur try karte rehna padta hai. "
        "Toh next time jab koi naya AI trend dekho, turant try kar lena, pata nahi wahi tumhara "
        "favourite tool ban jaye. Comment mein batana tumhara favourite AI tool kaunsa hai!"
    )

    if not GEMINI_API_KEY:
        print("No GEMINI_API_KEY set - using fallback script.")
        return fallback_title, fallback_script

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    instruction = (
        "Generate a trending script for an AI influencer YouTube Short. "
        "Write it EXACTLY the way a young, casual Pakistani/Indian social media influencer girl "
        "talks on camera - natural spoken Hindi/Urdu mixed with the common, everyday English words "
        "such speakers naturally drop in (things like 'guys', 'literally', 'trust me', 'basically', "
        "'so', 'obviously', 'honestly', 'content', 'vibe' - use a few of these naturally, don't force all of them). "
        "Write it in Roman/Latin script only. "
        "\n\nCRITICAL STYLE RULES:\n"
        "1. It must sound like ONE continuous, flowing spoken thought - like she is talking to a friend, "
        "not reading a list of facts. Use natural spoken connectors (jaise 'toh', 'matlab', 'basically', "
        "'na', 'yaar', 'honestly') to link ideas smoothly.\n"
        "2. Avoid choppy, robotic, list-like sentences. Do NOT write it as separate isolated facts stitched "
        "together - it should flow like real conversation with varying sentence length (mix short punchy "
        "lines with a couple of slightly longer flowing ones).\n"
        "3. Use ONLY simple, everyday Hindi/Urdu words that a common person uses in daily speech. "
        "Do NOT use difficult, literary, or formal Hindi words (avoid words like 'raftaar', 'vigyan', "
        "'antarrashtriya') or difficult/classical Urdu words (avoid words like 'ehtemam', 'muntazir', "
        "'tabdeeli' wagera). Keep vocabulary as simple as normal daily conversation.\n"
        "4. Minimize commas and avoid unnecessary punctuation that creates unnatural pauses - write it "
        "so it can be read aloud smoothly in one breathable flow, not word-by-word.\n"
        "5. Keep sentences short-to-medium, natural spoken length - not textbook-formal.\n"
        "The script MUST take roughly 30-40 seconds to speak - about 90 to 130 words. "
        "Reply ONLY with valid JSON, no markdown, no code fences, in this exact shape: "
        '{"title": "catchy title", "script": "Hinglish voiceover script"}'
    )
    body = {"contents": [{"parts": [{"text": instruction}]}]}

    try:
        print("Asking Gemini for trending influencer script...")
        resp = requests.post(api_url, json=body, timeout=60)
        if resp.status_code != 200:
            print(f"Gemini API returned status code {resp.status_code}: {resp.text}")
            return fallback_title, fallback_script

        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()

        parsed = json.loads(text)
        return (
            str(parsed.get("title") or fallback_title).strip(),
            str(parsed.get("script") or fallback_script).strip(),
        )
    except Exception as e:
        print(f"Gemini error: {e}. Using fallbacks.")
        return fallback_title, fallback_script


async def _generate_edge_tts_async(script_text, output_path):
    communicate = edge_tts.Communicate(script_text, VOICE, rate=RATE, pitch=PITCH)
    await communicate.save(output_path)


def _clean_script_for_speech(text):
    """Symbols/emojis/extra punctuation hata do jo TTS ko choppy ya ajeeb bana dete hain."""
    import re
    text = re.sub(r"#\w+", "", text)              # hashtags
    text = re.sub(r"[*_~`]", "", text)             # markdown symbols
    text = re.sub(r"[\U0001F300-\U0001FAFF]", "", text)  # emojis
    text = re.sub(r"\.{2,}", ".", text)            # "..." -> "."
    text = re.sub(r",\s*,", ",", text)             # double commas
    text = re.sub(r"\s+", " ", text).strip()
    return text


def generate_voiceover(script_text):
    script_text = _clean_script_for_speech(script_text)
    print(f"Generating voiceover with Edge-TTS (voice={VOICE})...")
    try:
        asyncio.run(_generate_edge_tts_async(script_text, OUTPUT_AUDIO_FILE))
        if os.path.exists(OUTPUT_AUDIO_FILE):
            print("Successfully generated voiceover using Edge-TTS!")
            return OUTPUT_AUDIO_FILE
        else:
            print("Edge-TTS failed to produce the audio file.")
            return None
    except Exception as e:
        print(f"Edge-TTS generation failed: {e}")
        return None


BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
LIPSYNC_DOWNLOAD_DIR = "output/lipsync_raw"


def _hf_headers(token=None):
    headers = {"User-Agent": BROWSER_UA, "Accept": "*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _space_root_url(space, client=None):
    """Space ka base URL (client se, warna slug bana kar)."""
    src = getattr(client, "src", "") or ""
    if isinstance(src, str) and src.startswith("http"):
        return src.rstrip("/")
    slug = space.replace("/", "-").replace("_", "-").replace(".", "-").lower()
    return f"https://{slug}.hf.space"


def _extract_remote_file(result):
    """Gradio result se (url, server-side path) nikalo - list/dict/str sab handle karta hai."""
    node = result
    while isinstance(node, (list, tuple)) and node:
        node = node[0]

    url = None
    path = None

    if isinstance(node, dict):
        url = node.get("url")
        path = node.get("path") or node.get("name") or node.get("video")
        if isinstance(path, dict):
            url = url or path.get("url")
            path = path.get("path") or path.get("name")
    elif isinstance(node, str):
        if node.startswith("http"):
            url = node
        else:
            path = node

    return url, path


def _download_lipsync_output(url, remote_path, root, token, dest):
    """Output video ko khud download karo.

    gradio_client ka apna downloader purane '/file=' route par 403 Forbidden de
    deta hai (naye Gradio Spaces par route '/gradio_api/file=' hai). Isliye hum
    khud saare possible routes try karte hain, proper headers + HF token ke saath.
    """
    candidates = []
    if url:
        candidates.append(url)
    if remote_path:
        clean = str(remote_path).lstrip("/")
        candidates.extend([
            f"{root}/gradio_api/file={remote_path}",
            f"{root}/file={remote_path}",
            f"{root}/gradio_api/file={clean}",
            f"{root}/file={clean}",
        ])

    seen = set()
    ordered = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            ordered.append(c)

    tokens = [t for t in ([token] + [k for k in HF_KEYS if k.strip()]) if t]
    tokens.append(None)

    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)

    for link in ordered:
        for tok in tokens:
            try:
                resp = requests.get(
                    link,
                    headers=_hf_headers(tok),
                    stream=True,
                    timeout=300,
                    allow_redirects=True,
                )
                if resp.status_code == 200:
                    with open(dest, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=1024 * 256):
                            if chunk:
                                f.write(chunk)
                    if os.path.exists(dest) and os.path.getsize(dest) > 10000:
                        print(f"Lipsync video downloaded ({os.path.getsize(dest)} bytes) from: {link}")
                        return dest
                    print(f"Download se khali/chhoti file aayi: {link}")
                else:
                    print(f"Download failed [{resp.status_code}] -> {link}")
            except Exception as e:
                print(f"Download error on {link}: {e}")
            time.sleep(2)

    return None


def generate_lipsync_video(character_image, audio_path):
    if not GRADIO_AVAILABLE:
        print("gradio_client not installed - skipping lipsync step.")
        return None

    def make_client(space, token):
        """Client banao aur gradio ka auto-download BAND rakho (403 wali jagah)."""
        kwarg_options = []
        if token:
            kwarg_options += [
                {"hf_token": token, "download_files": False},
                {"token": token, "download_files": False},
                {"hf_token": token},
                {"token": token},
            ]
        kwarg_options += [{"download_files": False}, {}]

        last_error = None
        for kwargs in kwarg_options:
            try:
                return GradioClient(space, **kwargs)
            except TypeError as e:
                last_error = e
                continue
        raise last_error if last_error else RuntimeError("Gradio client ban hi nahi saka")

    tokens = [t for t in HF_KEYS if t.strip()]
    attempts = tokens + [None]

    for round_num in range(1, LIPSYNC_RETRY_ROUNDS + 1):
        print(f"--- Lipsync attempt round {round_num}/{LIPSYNC_RETRY_ROUNDS} ---")
        for space in LIPSYNC_SPACES:
            for token_idx, token in enumerate(attempts):
                try:
                    label = f"{space} (token {token_idx + 1})" if token else f"{space} (no token)"
                    print(f"Trying lipsync via Hugging Face Space: {label} ...")
                    client = make_client(space, token)

                    job = client.submit(
                        handle_file(character_image),
                        handle_file(audio_path),
                        LIPSYNC_CHECKPOINT,
                        False,
                        1,
                        0,
                        10,
                        0,
                        0,
                        api_name="/generate",
                    )
                    result = job.result(timeout=LIPSYNC_TIMEOUT_SECONDS)

                    url, remote_path = _extract_remote_file(result)

                    # Agar gradio ne khud hi file local save kar di ho to wahi use karo.
                    if remote_path and os.path.exists(remote_path):
                        print(f"Lipsync video generated successfully via {space}")
                        return remote_path

                    if not url and not remote_path:
                        print(f"Space ne koi file return nahi ki: {result}")
                        continue

                    root = _space_root_url(space, client)
                    dest = os.path.join(LIPSYNC_DOWNLOAD_DIR, f"lipsync_{int(time.time())}.mp4")
                    downloaded = _download_lipsync_output(url, remote_path, root, token, dest)

                    if downloaded:
                        print(f"Lipsync video generated successfully via {space}")
                        return downloaded

                    print("Video to ban gaya tha lekin download nahi ho saka (403/route issue). Agli koshish...")
                except Exception as e:
                    err_text = str(e)
                    if "PAUSED" in err_text or "invalid state" in err_text:
                        print(f"Space {space} is currently PAUSED/asleep - owner needs to restart it. Skipping to next option.")
                    else:
                        print(f"Lipsync attempt failed on {space} (token {token_idx + 1}): {e}")
                        traceback.print_exc()
                    time.sleep(3)
                    continue

        if round_num < LIPSYNC_RETRY_ROUNDS:
            print(f"All spaces failed this round. Waiting {LIPSYNC_ROUND_WAIT_SECONDS}s before retrying "
                  f"(Spaces sometimes wake back up)...")
            time.sleep(LIPSYNC_ROUND_WAIT_SECONDS)

    print("All Hugging Face Space attempts for lipsync failed after all retry rounds.")
    return None


def upload_to_youtube(video_path, title):
    if not YOUTUBE_AVAILABLE:
        print("YouTube libraries not available - skipping upload.")
        return

    client_id = os.getenv("YT_CLIENT_ID", "")
    client_secret = os.getenv("YT_CLIENT_SECRET", "")
    refresh_token = os.getenv("YT_REFRESH_TOKEN", "")

    if not client_id or not client_secret or not refresh_token:
        print("YouTube credentials missing - skipping upload.")
        return

    try:
        print("Uploading video to YouTube Shorts...")
        creds = Credentials(
            None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title,
                "description": "Generated automatically via AI Pipeline #Shorts",
                "tags": ["AI", "Shorts", "Tech"],
                "categoryId": "28"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%.")

        print(f"Video uploaded successfully! ID: {response.get('id')}")
    except Exception as e:
        print(f"YouTube upload failed: {e}")


def main():
    os.makedirs("output", exist_ok=True)
    
    # Step 1: Generate Script
    title, script_text = generate_influencer_script()
    print(f"Title: {title}")
    print(f"Script: {script_text}")

    # Step 2: Generate Voiceover
    audio_file = generate_voiceover(script_text)
    if not audio_file:
        print("Critical Error: Voiceover generation failed.")
        return

    # Step 3: Generate Lipsync Video
    if not os.path.exists(CHARACTER_IMAGE):
        print(f"Error: {CHARACTER_IMAGE} not found in repository root!")
        return

    video_output = generate_lipsync_video(CHARACTER_IMAGE, audio_file)
    lipsync_succeeded = bool(video_output and os.path.exists(video_output))

    if lipsync_succeeded:
        import shutil
        shutil.copy(video_output, OUTPUT_VIDEO_PATH)
        print(f"Final video ready at: {OUTPUT_VIDEO_PATH}")
    else:
        # Pehle yahan seedha ek silent black video ban ke YouTube pe upload ho jata tha.
        # Ab hum wo broken video YouTube pe post NHI karenge - sirf local debug ke liye bana rahe hain.
        print("Lipsync failed on all Spaces. Saving a local placeholder for debugging (NOT uploading it)...")
        os.system(f'ffmpeg -y -f lavfi -i color=c=black:s=1080x1920:d=15 -c:v libx264 {OUTPUT_VIDEO_PATH}')
        print("Critical Error: Real lipsync video nahi ban saka, isliye YouTube upload skip kiya ja raha hai.")
        print("Tip: GitHub Actions logs mein 'Lipsync attempt failed on ...' lines dekhein for exact reason.")
        return

    # Step 4: Upload to YouTube (sirf tab jab asal lipsync video ban chuka ho)
    upload_to_youtube(OUTPUT_VIDEO_PATH, title)


if __name__ == "__main__":
    main()
