# YouTube Shorts Bot

Automated multi-scene AI story short generator (Hindi voiceover) for YouTube Shorts.

## Providers (in try-order)
1. **PixVerse** - paid, needs credits (`PIXVERSE_KEY_1..4`)
2. **Kling** - paid/approved account (`KLING_API_KEY`)
3. **Replicate** - small free trial only, then paid (`REPLICATE_API_TOKEN`)
4. **Hugging Face free Spaces** - genuinely free, no card. Add `HF_TOKEN`,
   `HF_TOKEN_2`, `HF_TOKEN_3`, `HF_TOKEN_4` (tokens from separate free HF
   accounts) as GitHub secrets to stretch the daily free GPU quota.
   Optionally set `HF_VIDEO_SPACES` (comma-separated Space ids) to try more
   than one free Space.
5. **Pollinations.ai image + ffmpeg zoom (guaranteed fallback)** - fully
   free, no key needed. Keeps the pipeline from ever fully failing.

Voiceover: ElevenLabs (`ELEVEN_KEY_1..3`) first, falls back to free Google
TTS (`gTTS`) automatically if all ElevenLabs keys fail/run out.

## Config (env vars / GitHub secrets)
- `NUM_SCENES` (default `5`) - more scenes = longer final short. With
  ~6-8s of dialogue per scene, 5 scenes lands around 30-40 seconds.
- `HF_VIDEO_SPACES` (default `Wan-AI/Wan2.1`).
- `YT_PRIVACY_STATUS` (default `private`) - set to `public` once you're
  happy with output quality.

## Schedule
Runs automatically twice a day via the cron entries in
`.github/workflows/main.yml`, plus manual "Run workflow" from the Actions
tab. Each run also uploads `final_short.mp4` as a workflow artifact either
way, so you always have a copy even if YouTube upload is off/fails.

## YouTube auto-upload (optional, free)
By default the bot only produces the video file. To have it also post
straight to your YouTube channel (free - YouTube Data API v3, well within
the free daily quota for 2 uploads/day):

1. Run `get_youtube_refresh_token.py` **once, on your own computer** (not
   in GitHub Actions) - it walks you through free Google Cloud OAuth setup
   and prints three values.
2. Add those three values as GitHub repo secrets: `YT_CLIENT_ID`,
   `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
3. Videos upload as **private** by default so you can review quality
   first. Add a repo **Variable** (Settings -> Secrets and variables ->
   Actions -> Variables tab) named `YT_PRIVACY_STATUS` set to `public`
   once you're happy.

If you never set up the three `YT_*` secrets, the bot skips upload
automatically and nothing breaks - you just keep using the artifact
download like before.
