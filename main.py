def generate_hedra_video(audio_file_path, image_url):
    """Hedra API flow: Audio upload -> Character Job Submit -> Status Check -> Download Video"""
    print("\n--- Starting Hedra Video Generation ---")

    # Step A: Audio Asset Upload (Fixed headers structure)
    print("Uploading Audio to Hedra...")
    upload_url = f"{HEDRA_BASE_URL}/assets"
    
    # Header format updated to strictly send X-API-Key
    upload_headers = {
        "X-API-Key": HEDRA_API_KEY
    }

    try:
        with open(audio_file_path, "rb") as f:
            files = {"file": ("audio.mp3", f, "audio/mpeg")}
            data = {"type": "audio"}
            upload_res = requests.post(
                upload_url, headers=upload_headers, files=files, data=data
            )
    except Exception as e:
        print(f"File reading error: {e}")
        return None

    if upload_res.status_code not in [200, 201]:
        print(f"Audio upload failed! Code: {upload_res.status_code}")
        print(f"Response: {upload_res.text}")
        return None

    audio_data = upload_res.json()
    audio_asset_id = audio_data.get("id") or audio_data.get("url")
    print(f"Audio Uploaded. Asset Identifier: {audio_asset_id}")

    # Step B: Submit Video Generation Job
    print("Submitting Character Generation Request...")
    generate_url = f"{HEDRA_BASE_URL}/generations"
    payload = {
        "type": "video",
        "input": {
            "aspect_ratio": "9:16",
            "audio_url": audio_asset_id,
            "image_url": image_url
        }
    }

    # Custom json request headers
    job_headers = {
        "X-API-Key": HEDRA_API_KEY,
        "Content-Type": "application/json"
    }

    gen_res = requests.post(generate_url, json=payload, headers=job_headers)

    if gen_res.status_code not in [200, 201]:
        print(f"Generation Job Failed! Code: {gen_res.status_code}")
        print(f"Response: {gen_res.text}")
        return None

    job_id = gen_res.json().get("job_id") or gen_res.json().get("id")
    print(f"Job Submitted Successfully. Job ID: {job_id}")

    # Step C: Polling Video Processing Status
    status_url = f"{HEDRA_BASE_URL}/generations/{job_id}"

    while True:
        status_res = requests.get(status_url, headers=job_headers).json()
        job_status = status_res.get("status")

        if job_status == "completed":
            video_url = status_res.get("video_url") or status_res.get("url")
            print(f"\nSUCCESS: Video URL: {video_url}")

            video_data = requests.get(video_url).content
            output_video = "final_short.mp4"
            with open(output_video, "wb") as f:
                f.write(video_data)
            print(f"Saved locally as '{output_video}'")
            return output_video

        elif job_status in ["failed", "error"]:
            print(f"\nFAILED: Generation Error: {status_res.get('error')}")
            return None

        print("Processing video... Waiting 5 seconds.")
        time.sleep(5)
