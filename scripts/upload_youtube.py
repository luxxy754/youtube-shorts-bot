import os
import sys
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN", "")
YT_PRIVACY_STATUS = os.getenv("YT_PRIVACY_STATUS", "public")

def upload_to_youtube(file_path, title="AI Influencer Short"):
    if not YT_CLIENT_ID or not YT_CLIENT_SECRET or not YT_REFRESH_TOKEN:
        print("Error: YouTube OAuth credentials (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN) are missing in environment variables.")
        sys.exit(1)

    if not os.path.exists(file_path):
        print(f"Error: Video file not found at {file_path}")
        sys.exit(1)

    print("Authenticating with YouTube API...")
    credentials = Credentials(
        None,
        refresh_token=YT_REFRESH_TOKEN,
        client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token"
    )

    youtube = build("youtube", "v3", credentials=credentials)

    body = {
        "snippet": {
            "title": title,
            "description": "Generated & uploaded automatically via AI Influencer Bot #Shorts",
            "tags": ["AI", "Shorts", "Trending"],
            "categoryId": "22"  # People & Blogs
        },
        "status": {
            "privacyStatus": YT_PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)

    print(f"Uploading {file_path} to YouTube Shorts...")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    print(f"Upload complete! Video ID: {response.get('id')}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="output/short_video.mp4", help="Path to video file")
    parser.add_argument("--title", default="Aaj Ki Viral Baat! #Shorts", help="YouTube video title")
    args = parser.parse_args()

    upload_to_youtube(args.file, args.title)
