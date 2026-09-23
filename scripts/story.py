"""Cat story generator - VISUALS ONLY, no dialogue.

Cat meows, doesn't talk. So story is told through actions + expressions.
Each scene has 6 frame descriptions for choppy animation.
"""
import json
import os
import random
import re

import requests


THEMES = [
    "ek choti billi apni khoyi hui gend dhoondti hai",
    "ek kitten apni maa ke saath pehli baar dhoop mein khelti hai",
    "ek bhookhi billi khana dhoondte hue rasoi mein ghus jati hai",
    "ek sharmili billi naye puppy se dosti karti hai",
    "ek chhoti billi apni dum pakadne ki koshish karti hai",
    "ek kitten pehli baar barish dekhti hai",
    "ek billi apni favorite jagah pe soney ki koshish karti hai",
    "ek kitten titli pakadne ki koshish karti hai",
    "ek billi apne dost ke saath doodh peeti hai",
    "ek chhoti billi chhat pe baith ke duniya dekhti hai",
]

STYLE = (
    "Ultra-detailed 3D Pixar-style animated movie still, "
    "cinematic render, shot on virtual ARRI Alexa camera, "
    "subsurface skin scattering on fur, "
    "ray-traced soft shadows, ambient occlusion, "
    "volumetric warm sunlight with dust particles, "
    "physically-based rendering (PBR), 8K hyper-detailed fur texture, "
    "VERY CUTE fluffy kitten with BIG glossy expressive eyes, "
    "small pink nose, chubby rounded soft body, "
    "soft fluffy detailed fur with individual strands visible, "
    "expressive face showing clear emotion (happy / curious / surprised / warm), "
    "bright cheerful color palette, "
    "shallow depth of field with creamy bokeh, "
    "detailed clean background (sunny living room, cozy garden, warm kitchen), "
    "cinematic composition with rule of thirds, "
    "vertical 9:16 portrait framing, "
    "FRONT-FACING character centered in frame, face clearly visible, "
    "well lit, looking at camera, "
    "absolutely no text, no subtitles, no watermark, no logo, "
    "no humans, no scary elements, no violence, "
    "no 2D illustration, no anime, no sketch, no low-poly"
)

NEGATIVE = (
    "blurry, low quality, low resolution, jpeg artifacts, "
    "flat lighting, flat shading, plasticky, waxy, doll-like, "
    "extra limbs, extra arms, extra legs, extra eyes, extra tails, "
    "deformed face, distorted mouth, crooked eyes, "
    "cropped head, cropped body, off-center, "
    "text, watermark, logo, signature, "
    "human, person, hand, realistic photo, "
    "scary, dark, blood, violence, "
    "2d, cartoon flat, anime, manga, sketch, "
    "abstract, glitch, artifact, noise"
)

FALLBACK = {
    "title": "Choti Billi ki Gend 🐱🧶 #shorts",
    "description": "Ek choti billi apni khoyi hui gend dhoondti hai.",
    "hashtags": ["#cat", "#kitten", "#cute", "#animation", "#shorts", "#kids"],
    "keywords": ["cute cat animation", "kitten cartoon", "3d cat", "funny cat"],
    "character": (
        "a tiny fluffy orange tabby kitten with soft orange-and-white fur, "
        "BIG glossy black Pixar-style cartoon eyes with sparkly highlights, "
        "small pink nose, chubby rounded soft body, "
        "tiny stubby paws and small tail with white tip, "
        "expressive face showing wonder and curiosity, "
        "in a warm cozy sunlit living room with wooden floor and soft rug"
    ),
    "scenes": [
        {
            "visual": "The tiny orange kitten sits on a wooden floor, looking at a red yarn ball with BIG curious eyes. Medium shot, eye-level, FRONT-FACING, warm morning sunlight.",
            "sfx": "curious meow",
            "motions": [
                "sitting still, looking at ball",
                "head tilting slightly left",
                "leaning forward a bit",
                "one paw lifted",
                "paw reaching toward ball",
                "paw touching ball",
            ],
        },
        {
            "visual": "The tiny kitten reaches one paw toward the yarn ball, tilting head slightly. Close-up, FRONT-FACING, warm golden light.",
            "sfx": "playful meow",
            "motions": [
                "paw extended forward",
                "paw touching ball",
                "ball starting to move",
                "ball rolling slightly",
                "kitten leaning further",
                "both paws on ball",
            ],
        },
        {
            "visual": "The tiny kitten playfully bats the yarn ball with both front paws, eyes wide, tail up. Medium shot, FRONT-FACING, warm afternoon light.",
            "sfx": "playful chirp",
            "motions": [
                "batting ball with left paw",
                "ball flying left",
                "kitten head turned left",
                "batting ball with right paw",
                "ball flying right",
                "kitten standing, alert",
            ],
        },
        {
            "visual": "The tiny kitten happily hugs the yarn ball, eyes closed in joy, small smile. Close-up, FRONT-FACING, golden hour warm light.",
            "sfx": "happy purr",
            "motions": [
                "both paws on ball",
                "hugging ball close",
                "eyes starting to close",
                "eyes half closed",
                "eyes fully closed, smiling",
                "purring, hugging tight",
            ],
        },
    ],
    "music": "playful cinematic instrumental with ukulele, marimba, light drums, no vocals",
}


def _prompt(n_scenes, frames_per_scene):
    theme = random.choice(THEMES)
    return f"""
You are writing a SHORT, kids-friendly YouTube Shorts story about a
CUTE KITTEN in ultra-detailed Pixar 3D style.

IMPORTANT: The kitten does NOT talk. There is NO dialogue.
The story is told through ACTIONS and EXPRESSIONS only.
The kitten only makes natural sounds (meow, purr, chirp).

THEME: {theme}

Each scene is animated with {frames_per_scene} still frames showing
SLIGHT pose changes.

For each scene provide:
  1. "visual": ONE main description of the scene moment.
                Front-facing, face centered, cinematic framing.
  2. "sfx":    short cat sound description (meow, purr, chirp, etc.)
  3. "motions": list of {frames_per_scene} SHORT motion descriptions,
                each a TINY pose change from the previous frame.
                Example: ["sitting still", "head tilting", "leaning forward",
                          "paw lifting", "paw extended", "touching ball"]
                Keep the kitten EXACTLY the same, only pose changes.

CRITICAL RULES:
- ONLY the kitten. No humans. No dialogue. No text.
- Family friendly. No violence, no scary elements.
- Kitten appearance MUST stay identical across all frames.
- Simple clean background (living room, garden, kitchen).

Return ONLY valid JSON:

{{
  "title": "warm curiosity-driven title under 80 chars ending with #shorts",
  "description": "one or two short English sentences",
  "hashtags": ["#cat", "#kitten", "#cute", "#animation", "#shorts", "#kids"],
  "keywords": ["6-8 YouTube search phrases"],
  "character": "one VERY detailed English sentence about the kitten's exact appearance AND the setting",
  "scenes": [
    {{
      "visual": "English: main frozen moment with framing + lighting. 2 sentences.",
      "sfx": "short cat sound description",
      "motions": ["motion 1", "motion 2", ... {frames_per_scene} items total]
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


def _valid(story, n_scenes, frames_per_scene):
    if not isinstance(story, dict):
        return False
    if not story.get("title") or not story.get("character"):
        return False
    scenes = story.get("scenes")
    if not isinstance(scenes, list) or len(scenes) < n_scenes:
        return False
    for scene in scenes[:n_scenes]:
        if not isinstance(scene, dict):
            return False
        if not scene.get("visual"):
            return False
        motions = scene.get("motions")
        if not isinstance(motions, list):
            scene["motions"] = []
        while len(scene["motions"]) < frames_per_scene:
            scene["motions"].append("same pose, tiny variation")
    return True


def generate_story(n_scenes=4, frames_per_scene=6):
    prompt = _prompt(n_scenes, frames_per_scene)
    for name, function in (("Gemini", _gemini), ("Groq", _groq)):
        try:
            story = function(prompt)
            if _valid(story, n_scenes, frames_per_scene):
                story["scenes"] = story["scenes"][:n_scenes]
                print(f"Story idea from {name}: {story['title']}")
                return story
        except Exception as exc:
            print(f"{name} failed: {str(exc)[:250]}")

    print("Using built-in fallback story.")
    story = dict(FALLBACK)
    story["scenes"] = FALLBACK["scenes"][:n_scenes]
    for sc in story["scenes"]:
        if "motions" not in sc:
            sc["motions"] = [f"pose variant {i+1}" for i in range(frames_per_scene)]
    return story


def frame_prompt(story, scene_index, frame_index, total_frames):
    """Build image prompt for ONE frame of a scene."""
    scenes = story.get("scenes", [])
    if not scenes:
        return ""
    scene = scenes[scene_index % len(scenes)]
    character = story.get("character", "")
    base = scene.get("visual", "")
    motions = scene.get("motions", [])
    motion = motions[frame_index % len(motions)] if motions else ""

    prompt = f"""
{STYLE}

CHARACTER (must match EXACTLY in every frame):
{character}

SCENE (base composition):
{base}

FRAME {frame_index + 1} of {total_frames}:
Tiny pose change: {motion}

IMPORTANT:
- Character must look IDENTICAL to all other frames (same fur, eyes, color)
- Only the POSE changes slightly
- Same camera angle, same lighting, same background
- Face FRONT-FACING, centered, well lit

NEGATIVE: {NEGATIVE}
"""
    return " ".join(prompt.split())


def scene_sfx(story, index):
    scenes = story.get("scenes", [])
    if not scenes:
        return "cute cat meow"
    return scenes[index % len(scenes)].get("sfx", "cute cat meow")
