# AI Cat Shorts Bot

Makes 15s funny 3D Pixar-style animal Shorts (no voiceover, only sound effects + music) and uploads them to YouTube.

Flow: Gemini (Groq backup) writes story -> Replicate makes 3 vertical clips -> ElevenLabs makes cat/engine sfx + music -> ffmpeg joins -> YouTube upload.
If Replicate fails, a free Pollinations image + zoom is used for that scene.

## Secrets (Settings -> Secrets and variables -> Actions)
REPLICATE_API_TOKEN, GEMINI_API_KEY, GROQ_API_KEY (backup), POLLINATIONS_API_KEY (backup),
ELEVEN_KEY_1..3, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN

## Variables (optional)
- `YT_PRIVACY_STATUS` = public / private / unlisted (default public)

## Env tweaks (in main.yml `env:`)
`NUM_SCENES` (3), `CLIP_SECONDS` (5), `MUSIC_VOLUME` (0.30), `VIDEO_MODELS` (bytedance/seedance-1-lite,minimax/video-01)

## Own music
Put royalty-free `.mp3` files in `assets/music/`; one is picked at random instead of AI music.

## Run
Actions tab -> AI Shorts Bot -> Run workflow (tick dry_run to skip upload). Video is always saved as an artifact.
