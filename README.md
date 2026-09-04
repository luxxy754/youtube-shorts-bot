# YouTube Shorts Bot

Automated 2-scene(+) AI story short generator (Hindi voiceover) for YouTube Shorts.

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

## Config
- `NUM_SCENES` (default `5`) - more scenes = longer final short. With
  ~6-8s of dialogue per scene, 5 scenes lands around 30-40 seconds.
- `HF_VIDEO_SPACES` (default `Wan-AI/Wan2.1`).

## Schedule
Runs automatically twice a day via the cron entries in
`.github/workflows/main.yml`, plus manual "Run workflow" from the Actions tab.
Each run uploads `final_short.mp4` as a workflow artifact - upload to your
YouTube channel is a separate step (not automated here).
