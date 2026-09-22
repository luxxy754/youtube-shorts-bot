"""Viral short story generator for kids.
Creates fast, visual, dialogue-free stories designed for vertical Shorts.
"""
import json
import os
import random
import re

import requests


# Kids-friendly themes — simple, warm, easy to understand
THEMES = [
    "a tiny kitten learns to share a toy with a little puppy friend",
    "a small duckling gets lost in a garden and a kind kitten helps it find its way",
    "a baby bunny discovers a colorful butterfly and follows it through a flower field",
    "a little kitten tries to reach a high shelf to get a cookie for its friend",
    "a puppy learns that taking a nap is important after playing all day",
    "a kitten makes friends with a little bird who is learning to fly",
    "a little animal learns to say sorry after making a small mistake",
    "a kitten helps a sad friend feel happy again with a gentle hug",
    "a puppy learns to wait patiently for its food and gets a surprise",
    "a kitten discovers that being different is okay and makes a new friend",
    "a small puppy finds a lost baby animal and helps it get home safely",
    "a cute kitten secretly follows a delivery cart and causes funny trouble",
    "a tiny animal tries to copy a bigger animal and creates a funny ending",
    "a little duck follows a kitten into a gentle adventure",
    "a small puppy protects a tiny duckling from a harmless funny situation",
]


# Pixar-style 3D for kids — warm, cute, simple
STYLE = (
    "Pixar-style 3D animated short film for young children, "
    "very cute stylized animals with soft rounded shapes, "
    "big friendly eyes, warm and expressive faces, "
    "soft colorful fur, bright cheerful colors, "
    "gentle lighting with soft shadows, "
    "simple clear backgrounds, "
    "smooth slow movements, "
    "child-friendly camera angles, "
    "vertical 9:16 composition, "
    "no text, no subtitles, no watermark, "
    "no scary elements, no violence, no humans, "
    "no 2D illustration, no anime, no realistic rendering"
)


FALLBACK = {
    "title": "The Tiny Kitten and the Lost Duckling 🥹🐱 #shorts",
    "description": "A tiny kitten helps a little duckling find its way home.",
    "hashtags": [
        "#cat", "#kitten", "#animals", "#cute", "#funny",
        "#animation", "#3danimation", "#shorts", "#kids"
    ],
    "keywords": [
        "cute kitten animation for kids",
        "funny animal short",
        "3d animal animation",
        "cute cat story for children",
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
            "visual": "The tiny orange tabby kitten notices the little yellow duckling alone beside a small puddle, freezes for a moment and looks toward it with worried wide eyes while the camera slowly pushes toward the kitten.",
            "sfx": "soft surprised gasp and tiny duck chirp"
        },
        {
            "visual": "The tiny orange tabby kitten carefully runs toward the little yellow duckling and places one paw in front of it as a harmless rolling leaf approaches, while the camera tracks low beside the kitten.",
            "sfx": "quick soft footsteps and leaf rustle"
        },
        {
            "visual": "The little yellow duckling suddenly hugs the tiny orange tabby kitten, and the kitten looks completely surprised before giving a proud little smile, as the camera quickly pushes into their happy faces.",
            "sfx": "cute chirp followed by a soft happy sparkle sound"
        },
        {
            "visual": "The tiny orange tabby kitten proudly walks away with the little yellow duckling following directly behind, but the kitten suddenly slips on the harmless puddle and looks embarrassed at the camera while the duckling reacts with wide eyes.",
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
Create ONE highly visual viral YouTube Shorts story for YOUNG CHILDREN.

THEME:
{theme}

The video must feel like a modern cinematic 3D animal short for kids.

IMPORTANT STORY STYLE:
- No dialogue.
- No voiceover.
- Story must be understandable purely from body language and visuals.
- Family friendly. Safe for kids.
- No violence, blood, weapons, horror, or anything scary.
- Start with an immediate visual hook.
- Every scene must cause the next scene.
- Build gentle tension or curiosity.
- End with a funny, warm, or happy payoff.
- Make the final moment visually memorable and heartwarming.
- Characters must remain visually identical throughout the entire story.
- Keep emotions clear: happy, sad, surprised, friendly, warm.

STRUCTURE:
Scene 1 = immediate hook / gentle problem.
Scene 2 = character tries to help or attempt something.
Scene 3 = situation escalates or almost works.
Scene 4 = warm/funny payoff.

Each scene is approximately 3-5 seconds.

For EVERY scene:
- Describe ONE clear dominant physical action.
- Mention the exact character description when needed.
- Use natural animal body movement.
- Give ONE camera movement.
- Give a clear facial expression.
- Keep the number of props very low.
- Do not introduce unnecessary characters.
- Do not change fur color, eye color, body size or environment.
- Do not use confusing pronouns.
- Keep it simple enough for a 4-year-old to follow.

Return ONLY valid JSON:

{{
  "title": "warm curiosity-driven title under 80 characters ending with #shorts",
  "description": "one or two short warm sentences",
  "hashtags": ["#cat", "#animals", "#cute", "#animation", "#shorts", "#kids"],
  "keywords": [
    "6-8 YouTube search phrases for kids animal videos"
  ],
  "character": "one detailed sentence containing the exact appearance of every main character and the main environment",
  "scenes": [
    {{
      "visual": "one concrete cinematic shot describing action, expression and one camera movement",
      "sfx": "short sound effect description"
    }}
  ],
  "music": "short description of warm playful instrumental music"
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
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    response = requests.post(
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
    response.raise_for_status()
    text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(_clean(text))


def _groq(prompt):
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        return None
    response = requests.post(
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
    response.raise_for_status()
    text = response.json()["choices"][0]["message"]["content"]
    return json.loads(_clean(text))


def _valid(story, n_scenes):
    if not isinstance(story, dict):
        return False
    if not story.get("title") or not story.get("character"):
        return False
    scenes = story.get("scenes")
    if not isinstance(scenes, list) or len(scenes) < n_scenes:
        return False
    for scene in scenes[:n_scenes]:
        if not isinstance(scene, dict) or not scene.get("visual"):
            return False
    return True


def generate_story(n_scenes=4):
    prompt = _prompt(n_scenes)
    for name, function in (("Gemini", _gemini), ("Groq", _groq)):
        try:
            story = function(prompt)
            if _valid(story, n_scenes):
                story["scenes"] = story["scenes"][:n_scenes]
                print(f"Story idea from {name}: {story['title']}")
                return story
        except Exception as exc:
            print(f"{name} failed: {str(exc)[:250]}")

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

This is shot {index + 1} of a continuous short film for young children.

The character appearance MUST remain identical to previous shots.

KIDS-FRIENDLY REQUIREMENTS:
- The action must be simple and easy to understand for a 4-year-old.
- Show clear emotions: happy, sad, surprised, friendly, warm.
- No confusing or scary elements.
- Warm, cozy feeling throughout.
- The animal's face should be clearly visible and expressive.

Prioritize:
- believable animal anatomy
- smooth gentle body movement
- expressive friendly face
- clear readable action
- soft cinematic lighting
- cute stylized fur
- natural soft shadows
- gentle camera movement
- vertical 9:16 framing
- full subject visibility

NEGATIVE:
text, subtitles, watermark, logo, human, extra limbs,
extra eyes, duplicated animal, distorted face, deformed paws,
floating objects, cropped head, cropped body, flat illustration,
2D drawing, anime, sketch, low quality, blurry frame,
scary, dark, violence, blood

Generate ONLY the visual shot.
"""
    return " ".join(prompt.split())


def scene_sfx(story, index):
    scenes = story.get("scenes", [])
    if not scenes:
        return ""
    return scenes[index % len(scenes)].get("sfx", "light gentle sound effect")


def music_prompt(story):
    return story.get("music", FALLBACK["music"])
