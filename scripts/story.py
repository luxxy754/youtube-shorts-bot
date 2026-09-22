"""Viral short story generator.
Creates fast, visual, dialogue-free stories designed for vertical Shorts.
"""
import json
import os
import random
import re

import requests


THEMES = [
    "a tiny orange kitten accidentally becomes the hero of a busy city",
    "a small puppy tries to protect a tiny duck from a harmless funny situation",
    "a baby animal discovers a strange object and gets into escalating trouble",
    "a tiny kitten tries to impress a little puppy but everything goes hilariously wrong",
    "a little duck follows a kitten into an unexpected adventure",
    "a small puppy finds a lost baby animal and tries to help it get home",
    "a cute kitten secretly follows a delivery cart and causes a chain reaction of funny events",
    "a tiny animal tries to copy a bigger animal and creates an unexpected funny ending",
    "a cute kitten gets into a harmless misunderstanding with another animal",
    "a small animal saves the day in an unexpected and funny way",
]


STYLE = (
    "high-end cinematic 3D animated short film, polished feature-quality CGI, "
    "semi-realistic cute animals, realistic detailed fur and feathers, natural animal anatomy, "
    "expressive eyes with realistic reflections, believable facial expressions, "
    "cinematic physically based lighting, soft global illumination, subtle volumetric light, "
    "realistic shadows, detailed environments, cinematic depth of field, "
    "smooth natural body animation, believable weight and motion, "
    "dynamic camera cinematography, vertical 9:16 composition, "
    "strong visual storytelling, rich cinematic color grading, "
    "no text, no subtitles, no watermark, no logos, no humans, no dialogue, "
    "no 2D illustration, no anime, no flat cartoon, no sketch"
)


FALLBACK = {
    "title": "The Tiny Hero Nobody Expected 🥹🐱 #shorts",
    "description": "A tiny kitten gets into trouble while trying to help a little duck.",
    "hashtags": [
        "#cat", "#kitten", "#animals", "#cute", "#funny",
        "#animation", "#3danimation", "#shorts"
    ],
    "keywords": [
        "cute kitten animation",
        "funny animal short",
        "3d animal animation",
        "cute cat story",
        "viral animal shorts",
        "funny kitten video",
        "cinematic animation",
        "youtube shorts"
    ],
    "character": (
        "a tiny fluffy orange tabby kitten with soft orange-and-white fur, "
        "large expressive green eyes, small rounded ears and a tiny blue collar, "
        "standing beside a very small yellow duckling with soft yellow feathers, "
        "orange beak and glossy black eyes, in a colorful realistic-looking small town"
    ),
    "scenes": [
        {
            "visual": (
                "The tiny orange tabby kitten notices the frightened little yellow duckling "
                "alone beside a small roadside puddle, freezes for a moment and looks toward it "
                "with worried wide eyes while the camera slowly pushes toward the kitten."
            ),
            "sfx": "soft surprised gasp and tiny duck chirp"
        },
        {
            "visual": (
                "The tiny orange tabby kitten carefully runs toward the little yellow duckling "
                "and places one paw in front of it as a harmless rolling object approaches, "
                "while the camera tracks low beside the kitten."
            ),
            "sfx": "quick footsteps and rolling object sound"
        },
        {
            "visual": (
                "The little yellow duckling suddenly hugs the tiny orange tabby kitten, "
                "and the kitten looks completely surprised before giving a proud little smile, "
                "as the camera quickly pushes into their happy faces."
            ),
            "sfx": "cute chirp followed by a soft happy sparkle sound"
        },
        {
            "visual": (
                "The tiny orange tabby kitten proudly walks away with the little yellow duckling "
                "following directly behind, but the kitten suddenly slips on the harmless puddle "
                "and looks embarrassed at the camera while the duckling reacts with wide eyes."
            ),
            "sfx": "small slip sound and comedic pop"
        },
    ],
    "music": (
        "fast playful cinematic instrumental with pizzicato strings, marimba, "
        "light drums, soft bass and short comedic accents, no vocals"
    ),
}


def _prompt(n_scenes):
    theme = random.choice(THEMES)

    return f"""
Create ONE highly visual viral YouTube Shorts story.

THEME:
{theme}

The video must feel like a modern cinematic 3D animal short rather than a slideshow.

IMPORTANT STORY STYLE:
- No dialogue.
- No voiceover.
- Story must be understandable purely from body language and visuals.
- Family friendly.
- No violence, blood, weapons or horror.
- Start with an immediate visual hook.
- Every scene must cause the next scene.
- Build tension or curiosity.
- End with a funny, emotional or unexpected payoff.
- Make the final moment visually memorable.
- Characters must remain visually identical throughout the entire story.

STRUCTURE:
Scene 1 = immediate hook / problem.
Scene 2 = character attempts something.
Scene 3 = situation escalates or almost succeeds.
Scene 4 = unexpected payoff / funny ending.

Each scene is approximately 3-5 seconds.

For EVERY scene:
- Describe ONE clear dominant physical action.
- Mention the exact character description when needed.
- Use natural animal body movement.
- Give ONE camera movement.
- Give a clear facial expression.
- Keep the number of props very low.
- Do not introduce unnecessary characters.
- Do not change clothes, fur color, eye color, body size or environment without a story reason.
- Do not use pronouns like "he", "she", "it" when character identity could become ambiguous.
- Avoid complicated simultaneous actions.

Return ONLY valid JSON:

{{
  "title": "curiosity-driven title under 80 characters ending with #shorts",
  "description": "one or two short engaging sentences",
  "hashtags": ["#cat", "#animals", "#funny", "#cute", "#animation", "#shorts"],
  "keywords": [
    "6-8 YouTube search phrases"
  ],
  "character": "one detailed sentence containing the exact appearance of every main character and the main environment",
  "scenes": [
    {{
      "visual": "one concrete cinematic shot describing action, expression and one camera movement",
      "sfx": "short sound effect description"
    }}
  ],
  "music": "short description of energetic cinematic instrumental music"
}}

The scenes array MUST contain exactly {n_scenes} scenes.
"""


def _clean(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text).strip()
    return text


def _gemini(prompt):
    key = os.getenv("GEMINI_API_KEY", "").strip()

    if not key:
        return None

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )

    response = requests.post(
        url,
        params={"key": key},
        json={
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 1.0,
            },
        },
        timeout=90,
    )

    response.raise_for_status()

    text = response.json()["candidates"][0]["content"]["parts"][0]["text"]

    return json.loads(_clean(text))


def _groq(prompt):
    key = os.getenv("GROQ_API_KEY", "").strip()

    if not key:
        return None

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {key}"
        },
        json={
            "model": os.getenv(
                "GROQ_MODEL",
                "llama-3.3-70b-versatile"
            ),
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "response_format": {
                "type": "json_object"
            },
            "temperature": 1.0,
        },
        timeout=90,
    )

    response.raise_for_status()

    text = response.json()["choices"][0]["message"]["content"]

    return json.loads(_clean(text))


def _valid(story, n_scenes):
    if not isinstance(story, dict):
        return False

    if not story.get("title"):
        return False

    if not story.get("character"):
        return False

    scenes = story.get("scenes")

    if not isinstance(scenes, list):
        return False

    if len(scenes) < n_scenes:
        return False

    for scene in scenes[:n_scenes]:
        if not isinstance(scene, dict):
            return False

        if not scene.get("visual"):
            return False

    return True


def generate_story(n_scenes=4):
    prompt = _prompt(n_scenes)

    for name, function in (
        ("Gemini", _gemini),
        ("Groq", _groq),
    ):
        try:
            story = function(prompt)

            if _valid(story, n_scenes):
                story["scenes"] = story["scenes"][:n_scenes]

                print(
                    f"Story idea from {name}: "
                    f"{story['title']}"
                )

                return story

        except Exception as exc:
            print(
                f"{name} failed: "
                f"{str(exc)[:250]}"
            )

    print("Using built-in fallback story.")

    story = dict(FALLBACK)

    story["scenes"] = FALLBACK["scenes"][:n_scenes]

    return story


def scene_prompt(story, index):
    scenes = story.get("scenes", [])

    if not scenes:
        return ""

    scene = scenes[index % len(scenes)]

    character = story.get("character", "")

    visual = scene.get("visual", "")

    prompt = f"""
{STYLE}

CHARACTER CONTINUITY:
{character}

CURRENT SHOT:
{visual}

This is shot {index + 1} of a continuous short film.

The character appearance MUST remain identical to previous shots.

Prioritize:
- believable animal anatomy
- smooth body movement
- expressive face
- clear readable action
- cinematic lighting
- realistic fur
- natural shadows
- cinematic camera movement
- vertical 9:16 framing
- full subject visibility
- strong foreground/background separation

NEGATIVE:
text, subtitles, watermark, logo, human, extra limbs,
extra eyes, duplicated animal, distorted face, deformed paws,
floating objects, cropped head, cropped body, flat illustration,
2D drawing, anime, sketch, low quality, blurry frame

Generate ONLY the visual shot.
"""

    return " ".join(prompt.split())


def scene_sfx(story, index):
    scenes = story.get("scenes", [])

    if not scenes:
        return ""

    return scenes[index % len(scenes)].get(
        "sfx",
        "light cinematic sound effect"
    )


def music_prompt(story):
    return story.get(
        "music",
        FALLBACK["music"]
    )
