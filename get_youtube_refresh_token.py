# Run this ONCE on your own computer (NOT inside GitHub Actions) to get a
# YouTube upload refresh token for the bot. Fully free, no card needed.
#
# STEPS:
# 1. Go to https://console.cloud.google.com/ -> create a project (free).
# 2. In "APIs & Services" -> "Library", enable "YouTube Data API v3".
# 3. In "APIs & Services" -> "Credentials" -> "Create Credentials" ->
#    "OAuth client ID" -> Application type "Desktop app". Download the
#    JSON file it gives you.
# 4. Save that downloaded file as client_secret.json next to this script.
# 5. Install the one extra package this local script needs:
#       pip install google-auth-oauthlib
# 6. Run:
#       python get_youtube_refresh_token.py
#    A browser window opens - log in with the Google account that OWNS
#    the YouTube channel you want the bot to upload to.
# 7. Copy the three printed values into your GitHub repo's
#    Settings -> Secrets and variables -> Actions, as:
#       YT_CLIENT_ID
#       YT_CLIENT_SECRET
#       YT_REFRESH_TOKEN
#
# You only need to do this once - the refresh token keeps working until
# you revoke it.

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0)

print("\n=== Save these as GitHub repo secrets ===")
print("YT_CLIENT_ID     =", creds.client_id)
print("YT_CLIENT_SECRET =", creds.client_secret)
print("YT_REFRESH_TOKEN =", creds.refresh_token)
