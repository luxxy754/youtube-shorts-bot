"""Viral animal Shorts story generator.

Keeps the existing upload/automation pipeline intact. Only story + visual prompt
logic lives here, so the same generator can keep producing new videos automatically.
"""
import json
import os
import random
import re

import requests

# Topics are deliberately visual: they can be understood without dialogue/voiceover.
THEMES = [
    "a tiny orange cat secretly takes a sleepy duckling on a wild shopping-cart ride",
    "a tiny orange cat tries to hide a giant strawberry from a hungry puppy",
    "a tiny orange cat finds a baby penguin stuck inside a cardboard box and tries to help",
    "a tiny orange cat challenges a clever squirrel to a ridiculous cookie race",
    "a tiny orange cat steals a giant balloon and accidentally gets pulled into the sky",
    "a tiny orange cat tries to rescue a baby chick from a runaway toy car",
    "a tiny orange cat discovers a tiny door in the garden and opens it to a funny surprise",
    "a tiny orange cat tries to impress a duckling with a tiny red scooter",
    "a tiny orange cat guards a giant fish while a sneaky puppy keeps trying to grab it",
    "a tiny orange cat finds a mysterious glowing egg and gets a hilarious surprise",
    "a tiny orange cat tries to become a delivery driver with a sleepy puppy passenger",
    "a tiny orange cat and a baby duck discover a giant watermelon that starts rolling downhill",
]

# The visual language is intentionally more cinematic/realistic than the old generic
# cartoon prompts. This is applied after the AI writes each individual shot.
STYLE = (
    "high-end cinematic 3D CGI animated short, polished modern viral social-media animation, "
    "semi-realistic cute animals with believable anatomy, detailed soft fur and feathers, "
    "expressive glossy eyes with natural catchlights, physically based materials, "
    "soft global illumination, cinematic rim light, rich but natural colors, subtle depth of field, "
    "smooth believable character motion, strong readable poses, dynamic camera movement, "
    "professional feature-animation lighting, crisp details, vertical 9:16 composition, "
    "full characters visible and safely inside frame, subject centered with clean background, "
    "no text, no captions, no logo, no watermark, no humans, no dialogue, no speech bubbles, "
    "not anime, not flat 2D, not a drawing, not a sketch, not a poster"
)

NEGATIVE = (
    "avoid deformed anatomy, extra limbs, duplicate animals, changing fur color, changing clothes, "
    "cropped heads, cropped feet, extreme close-up, frozen pose, blurry face, text, watermark, logo"
)

FALLBACK = {
    "title": "The Cat Had ONE Job... 😳🐱 #shorts",
    "description": "A tiny cat tries to help a duckling... but the plan goes completely wrong. Wait for the ending!",
    "hashtags": ["#cat", "#animals", "#funny", "#ai", "#animation", "#viral", "#shorts"],
    "keywords": [
        "funny cat short", "cute animal animation", "viral ai animals",
        "3d animated short", "funny animal story", "cat and duck", "youtube shorts",
    ],
    "character": (
        "A tiny fluffy orange tabby kitten with a white muzzle, white chest, emerald-green eyes and a small red collar; "
        "a tiny round yellow duckling with a bright orange beak and glossy black eyes; the kitten is about twice the duckling's height; "
        "both live in a colorful sunny village garden with warm morning light."
    ),
    "scenes": [
        {
            "visual": "the orange kitten notices the duckling beside a huge strawberry, freezes with wide worried eyes, then points toward the strawberry with one paw; camera slowly pushes toward the kitten's face",
            "sfx": "tiny surprised gasp and soft sparkle chime",
        },
        {
            "visual": "the orange kitten grabs the strawberry and struggles to pull it across the garden while the duckling watches with a shocked open-beak expression; camera tracks sideways with the kitten",
            "sfx": "cartoon dragging squeak and quick footsteps",
        },
        {
            "visual": "the strawberry suddenly rolls downhill and the orange kitten chases after it with panicked wide eyes while the duckling looks stunned; camera rapidly follows the rolling strawberry at a low angle",
            "sfx": "fast rolling rumble, tiny paws running, comedic pop",
        },
    ],
    "music": "fast playful instrumental cartoon score, pizzicato strings, marimba, light drums and bouncy bass, energetic 125 BPM, no vocals",
}


def _prompt(n_scenes):
    theme = random.choice(THEMES)
    return f"""Create ONE highly engaging viral YouTube Short concept for a family-friendly AI animated animal video.
Core idea: {theme}.

The video must work WITHOUT dialogue, voiceover or on-screen text. The story must be understandable from body language, facial expressions, camera movement, sound effects and music alone.
Use a simple escalating structure: INSTANT HOOK -> clear goal/problem -> escalation -> surprising funny payoff.
The first scene must make the viewer curious immediately. The final scene must contain the strongest visual surprise and should feel loop-friendly.

Create exactly {n_scenes} shots. Each shot is approximately 5 seconds.

SHOT RULES:
- Each visual is ONE continuous shot in present tense.
- Use concrete physical actions that a video model can animate.
- ONE dominant action per shot. Do not give both animals separate complicated actions.
- Always identify the animal by its exact appearance, not pronouns such as he/it.
- Keep the same characters, colors, clothing/accessories and location throughout all shots.
- Include one clear facial emotion in every shot.
- Include exactly ONE main camera movement per shot: push-in, tracking, orbit, crane, pan, low-angle follow, etc.
- Keep important characters fully visible; avoid actions near frame edges.
- Do not describe rendering style in the visual field; it is added separately.
- No humans, dialogue, subtitles, captions or text.
- Keep props simple: maximum one important prop per shot.

Return ONLY valid JSON with exactly these keys:
{{
  "title": "curiosity-driven title under 70 characters, 1-2 emojis, ending with #shorts",
  "description": "one or two short natural sentences that create curiosity",
  "hashtags": ["7 relevant hashtags including #shorts"],
  "keywords": ["7 natural YouTube search phrases"],
  "character": "one detailed reusable sentence defining exact animal appearance, colors, accessories, size relationship and environment",
  "scenes": [
    {{"visual": "one concrete 5-second action + one camera move + one facial emotion", "sfx": "short sound effect description"}}
  ],
  "music": "short description of energetic instrumental background music with real instruments and approximate BPM, no vocals"
}}
The scenes array MUST contain exactly {n_scenes} items."""


def _clean(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    return re.sub(r"\s*```$", "", text).strip()


def _gemini(prompt):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    r = requests.post(
        url,
        params={"key": key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 1.0,
            },
        },
        timeout=90,
    )
    r.raise_for_status()
    return json.loads(_clean(r.json()["candidates"][0]["content"]["parts"][0]["text"]))


def _groq(prompt):
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        return None
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 1.0,
        },
        timeout=90,
    )
    r.raise_for_status()
    return json.loads(_clean(r.json()["choices"][0]["message"]["content"]))


def _valid(story, n):
    return (
        isinstance(story, dict)
        and bool(story.get("title"))
        and bool(story.get("character"))
        and isinstance(story.get("scenes"), list)
        and len(story["scenes"]) >= n
        and all(isinstance(s, dict) and s.get("visual") for s in story["scenes"][:n])
    )


def generate_story(n_scenes=3):
    prompt = _prompt(n_scenes)
    for name, fn in (("Gemini", _gemini), ("Groq", _groq)):
        try:
            story = fn(prompt)
            if _valid(story, n_scenes):
                story["scenes"] = story["scenes"][:n_scenes]
                print(f"Story idea from {name}: {story['title']}")
                return story
        except Exception as exc:  # noqa: BLE001
            print(f"{name} failed: {exc}")

    print("Using built-in fallback story.")
    story = dict(FALLBACK)
    story["scenes"] = FALLBACK["scenes"][:n_scenes]
    return story


def scene_prompt(story, scene):
    """Put character continuity first because many video/image models weight early text."""
    return (
        f"CHARACTER AND WORLD CONTINUITY: {story['character']} "
        f"SHOT: {scene['visual']} "
        f"VISUAL STYLE: {STYLE}. "
        f"NEGATIVE CONSTRAINTS: {NEGATIVE}."
    )
