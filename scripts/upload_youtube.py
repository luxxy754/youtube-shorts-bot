import argparse
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def upload_to_youtube(file_path, title):
    client_id = os.getenv("YT_CLIENT_ID", "").strip()
    client_secret = os.getenv("YT_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("YT_REFRESH_TOKEN", "").strip()
    privacy = os.getenv("YT_PRIVACY_STATUS", "public").strip().lower()

    if not all([client_id, client_secret, refresh_token]):
        raise RuntimeError("Missing YouTube OAuth secrets.")
    if privacy not in {"public", "private", "unlisted"}:
        privacy = "public"

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(path)

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    creds.refresh(Request())

    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = {
        "snippet": {
            "title": title[:100],
            "description": "Generated automatically via AI Influencer Bot #Shorts",
            "tags": ["AI", "Shorts", "Trending"],
            "categoryId": "22",
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True),
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload: {int(status.progress() * 100)}%")

    video_id = response.get("id")
    if not video_id:
        raise RuntimeError(f"YouTube returned no video ID: {response}")

    print(f"Uploaded: https://www.youtube.com/watch?v={video_id}")
    return video_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="output/short_video.mp4")
    parser.add_argument("--title", default="Aaj Ki Viral Baat! #Shorts")
    args = parser.parse_args()
    upload_to_youtube(args.file, args.title)
