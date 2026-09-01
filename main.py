import os
import time
import requests

# GitHub Secrets ya direct key se API key milegi
HEDRA_API_KEY = os.getenv("HEDRA_API_KEY", "apki_api_key_yahan")

# Correct Base URL for Hedra V3 API
BASE_URL = "https://api.hedra.com/v1"

headers = {
    "Authorization": f"Bearer {HEDRA_API_KEY}",
    "Content-Type": "application/json",
}


def generate_hedra_video(audio_file_path, image_url):
    print("Uploading Audio to Hedra...")

    # Step 1: Upload Audio Asset
    upload_url = f"{BASE_URL}/assets"
    upload_headers = {"Authorization": f"Bearer {HEDRA_API_KEY}"}

    with open(audio_file_path, "rb") as f:
        files = {"file": f}
        data = {"type": "audio"}
        upload_res = requests.post(
            upload_url, headers=upload_headers, files=files, data=data
        )

    if upload_res.status_code != 200:
        print(f"Audio upload failed: {upload_res.status_code}")
        print(upload_res.text)
        return None

    audio_asset_id = upload_res.json().get("id")
    print(f"Audio uploaded successfully. Asset ID: {audio_asset_id}")

    # Step 2: Submit Video Generation Job
    print("Submitting Character Video Job...")
    generate_url = f"{BASE_URL}/characters"

    payload = {
        "aspect_ratio": "9:16",
        "audio_asset_id": audio_asset_id,
        "image_url": image_url,
    }

    gen_res = requests.post(generate_url, json=payload, headers=headers)

    if gen_res.status_code not in [200, 201]:
        print(f"Generation Request Failed Code: {gen_res.status_code}")
        print(gen_res.text)
        return None

    job_id = gen_res.json().get("job_id")
    print(f"Job submitted successfully. Job ID: {job_id}")

    # Step 3: Wait for Video Processing
    status_url = f"{BASE_URL}/jobs/{job_id}"

    while True:
        status_res = requests.get(status_url, headers=headers).json()
        job_status = status_res.get("status")

        if job_status == "completed":
            video_url = status_res.get("video_url")
            print(f"Video Generated Successfully: {video_url}")

            # Video Download logic
            video_data = requests.get(video_url).content
            with open("final_short.mp4", "wb") as f:
                f.write(video_data)
            print("Saved as final_short.mp4")
            return "final_short.mp4"

        elif job_status == "failed":
            print(f"Video Generation Failed: {status_res.get('error')}")
            return None

        print("Video rendering in progress... waiting 5 seconds.")
        time.sleep(5)


# Execution Example:
# generate_hedra_video("hindi_audio.mp3", "https://image.pollinations.ai/prompt/3d%20funny%20character")
