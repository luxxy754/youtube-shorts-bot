"""Story generator for AI Shorts - IMAGE-focused prompts.

Each "scene" now produces ONE cinematic still image rather than a video.
So prompts focus on composition, framing, lighting, and character clarity
rather than motion descriptions.
"""
import json
import os
import random
import re

import requests


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
]


STYLE = (
    "Pixar-style 3D animated movie still, cinematic quality, "
    "very cute stylized animals with soft rounded shapes, "
    "big friendly expressive eyes, warm detailed faces, "
    "soft fluffy fur with visible individual strands, "
    "bright cheerful colors, warm golden-hour lighting, "
    "shallow depth of field with soft bokeh background, "
    "detailed but simple background, "
    "vertical 9:16 composition, full subject visible in frame, "
    "shot on cinema camera look, "
    "absolutely no text, no subtitles, no watermark, no logo, "
    "no humans, no scary elements, no violence, "
    "no 2D illustration, no anime, no sketch, no realistic photorealism"
)


FALLBACK = {
    "title": "The Tiny Kitten and the Lost Duckling 🥹🐱 #shorts",
    "description": "A tiny kitten helps a little duckling find its way home.",
    "hashtags": ["#cat", "#kitten", "#animals", "#cute", "#funny",
                 "#animation", "#3danimation", "#shorts", "#kids"],
    "keywords": ["cute kitten animation for kids", "funny animal short",
                 "3d animal animation", "cute cat story for children",
                 "viral animal shorts", "funny kitten video"],
    "character": (
        "a tiny fluffy orange tabby kitten with soft orange-and-white fur, "
        "large expressive green eyes, small rounded ears and a tiny blue collar, "
        "standing beside a very small yellow duckling with soft yellow feathers, "
        "orange beak and glossy black eyes"
    ),
    "scenes": [
        {"visual": "The tiny orange tabby kitten notices the little yellow duckling alone beside a small puddle, freezes with worried wide eyes. Medium shot, eye-level, warm afternoon light.",
         "sfx": "soft surprised gasp and tiny duck chirp"},
        {"visual": "The tiny orange tabby kitten carefully runs toward the little yellow duckling and places one paw in front of it protectively. Wide shot, low angle, golden light.",
         "sfx": "quick soft footsteps and leaf rustle"},
        {"visual": "The little yellow duckling hugs the tiny orange tabby kitten, and the kitten looks completely surprised before giving a proud little smile. Close-up, warm backlight.",
         "sfx": "cute chirp followed by a soft happy sparkle sound"},
        {"visual": "The tiny orange tabby kitten proudly walks away with the little yellow duckling following, but the kitten slips on a harmless puddle and looks embarrassed. Wide shot, comedic angle.",
         "sfx": "small slip sound and comedic pop"},
    ],
    "music": ("fast playful cinematic instrumental with pizzicato strings, "
              "marimba, light drums, soft bass, no vocals"),
}


def _prompt(n_scenes):
    theme = random.choice(THEMES)
    return f"""
You are writing a SHORT, kids-friendly YouTube Shorts story that will be
told using {n_scenes} CINEMATIC STILL IMAGES (not video clips).

THEME: {theme}

Each scene's "visual" field will be sent DIRECTLY to an image generator,
so it must describe a SINGLE FROZEN MOMENT in the story - a photograph,
not an action sequence. Focus on:
  - WHO is in frame and their exact facial expression
  - WHAT they are physically doing right now (one action only)
  - WHERE they are (simple, clean background)
  - CAMERA FRAMING (close-up / medium shot / wide shot, angle)
  - LIGHTING and mood

CRITICAL RULES:
- No dialogue. No voiceover. Story is understood from images alone.
- Family friendly. No violence, blood, weapons, horror, or scary elements.
- Character appearance MUST stay identical across all scenes.
- Each scene must clearly link to the next (before -> attempt -> climax -> payoff).
- Show clear emotions: happy, surprised, warm, gentle, funny.
- Keep props minimal. No extra characters beyond the main ones.
- Do NOT describe camera movement (no "camera pushes in") - only static framing.
- Do NOT describe motion like "runs toward" - describe the frozen pose instead.

Return ONLY valid JSON:

{{
  "title": "warm curiosity-driven title under 80 chars ending with #shorts",
  "description": "one or two short warm sentences",
  "hashtags": ["#cat", "#animals", "#cute", "#animation", "#shorts", "#kids"],
  "keywords": ["6-8 YouTube search phrases for kids animal videos"],
  "character": "one detailed sentence describing the EXACT appearance of every main character (fur color, eye color, size, collar, etc.) and the main environment",
  "scenes": [
    {{
      "visual": "ONE frozen moment: subject + expression + action pose + framing + lighting. 2-3 sentences max.",
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
        url, params={"key": key},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"responseMimeType": "application/json",
                                    "temperature": 1.0}},
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
        json={"model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
              "messages": [{"role": "user", "content": prompt}],
              "response_format": {"type": "json_object"},
              "temperature": 1.0},
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
    """Build the image-generation prompt for one scene."""
    scenes = story.get("scenes", [])
    if not scenes:
        return ""
    scene = scenes[index % len(scenes)]
    character = story.get("character", "")
    visual = scene.get("visual", "")

    prompt = f"""
{STYLE}

CHARACTER (must appear EXACTLY as described in every image):
{character}

THIS SCENE:
{visual}

Shot {index + 1} of a continuous short film. The animal's appearance must
match the previous shot EXACTLY (same fur, same eyes, same collar).

Requirements:
- Full subject visible, well framed, not cropped
- Cinematic, warm, cozy, kid-friendly
- Simple clean background so the character stands out
- Vertical 9:16 framing

Do NOT include any text, watermark, logo, or human.

NEGATIVE: text, watermark, logo, signature, human, extra limbs,
extra eyes, duplicated animal, distorted face, deformed paws,
floating objects, cropped head, flat illustration, 2D drawing,
anime, sketch, blurry, low quality, scary, dark, violence.
"""
    return " ".join(prompt.split())


def scene_sfx(story, index):
    scenes = story.get("scenes", [])
    if not scenes:
        return ""
    return scenes[index % len(scenes)].get("sfx", "light gentle sound effect")


def music_prompt(story):
    return story.get("music", FALLBACK["music"])
