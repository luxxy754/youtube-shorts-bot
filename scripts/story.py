"""Story generator for 'Talking Cat' Hindi/Urdu Shorts.

Each scene generates 6-8 frame descriptions with slight pose changes.
The AI image generator creates one image per frame, then FFmpeg
stitches them into a choppy animation.
"""
import json
import os
import random
import re

import requests


THEMES = [
    "ek choti billi apni khoyi hui gend ko dhoondti hai",
    "ek kitten apni maa ke saath pehli baar dhoop mein khelti hai",
    "ek bhookhi billi khana dhoondte hue rasoi mein ghus jati hai",
    "ek sharmili billi naye puppy se dosti karti hai",
    "ek chhoti billi apni dum pakadne ki koshish karti hai",
    "ek kitten pehli baar barish dekhti hai aur dar jati hai",
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
    "hashtags": ["#cat", "#kitten", "#cute", "#animation", "#shorts", "#kids", "#hindi"],
    "keywords": ["cute cat animation", "hindi kids story", "kitten cartoon", "3d cat"],
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
            "visual": "The tiny orange kitten sits on a wooden floor, looking at a red yarn ball with BIG curious eyes. Medium shot, eye-level, FRONT-FACING, warm morning sunlight through window.",
            "dialogue": "Yeh gend kahan se aayi?",
            "sfx": "curious meow"
        },
        {
            "visual": "The tiny kitten reaches one paw toward the yarn ball, tilting head slightly. Close-up, FRONT-FACING, warm golden light, creamy bokeh.",
            "dialogue": "Main ise pakadungi!",
            "sfx": "playful meow"
        },
        {
            "visual": "The tiny kitten playfully bats the yarn ball with both front paws, eyes wide, tail up. Medium shot, FRONT-FACING, warm afternoon light.",
            "dialogue": "Yeh toh bhaag rahi hai!",
            "sfx": "playful chirp"
        },
        {
            "visual": "The tiny kitten happily hugs the yarn ball, eyes closed in joy, small smile. Close-up, FRONT-FACING, golden hour warm light.",
            "dialogue": "Meri nayi gend!",
            "sfx": "happy purr"
        },
    ],
    "music": "playful cinematic instrumental with ukulele, marimba, light drums, no vocals",
}


def _prompt(n_scenes, frames_per_scene):
    theme = random.choice(THEMES)
    return f"""
You are writing a SHORT, kids-friendly YouTube Shorts story about a
CUTE KITTEN in ultra-detailed Pixar 3D style.

TARGET AUDIENCE: 3-6 year old Hindi/Urdu speaking children.
LANGUAGE: Roman Hindi/Urdu (like "Yeh kya hai?").
Use ONLY very simple, everyday words. NO difficult or formal words.

THEME: {theme}

Each scene will be animated using {frames_per_scene} still frames that
show SLIGHT pose changes so it looks like a choppy cartoon animation.

For each scene, provide:
  1. "base_visual": ONE main description of the scene moment.
                    Front-facing, face centered, cinematic framing.
  2. "dialogue":    ONE very short Hindi/Urdu line (max 8 words).
                    Simple, funny, kid-friendly. Roman script.
  3. "sfx":         short non-verbal sound effect (meow, purr, etc.)
  4. "motions":     list of {frames_per_scene} SHORT motion descriptions,
                    each describing a TINY change from the previous pose.
                    Example: ["paw reaching forward", "paw touching ball",
                              "ball rolling away", "kitten tilting head",
                              "kitten leaning forward", "kitten sitting up"]
                    Keep character EXACTLY the same, only pose changes.

CRITICAL RULES:
- Only the kitten as character. No humans. No other animals unless story needs.
- Family friendly. No violence, no horror, no scary elements.
- Kitten appearance MUST stay identical across all frames.
- Simple clean background (living room, garden, kitchen).
- Dialogue must be understandable by a 4-year-old.

Return ONLY valid JSON:

{{
  "title": "warm curiosity-driven Hindi/Urdu title under 80 chars ending with #shorts",
  "description": "one or two short Hindi/Urdu sentences",
  "hashtags": ["#cat", "#kitten", "#cute", "#animation", "#shorts", "#kids", "#hindi"],
  "keywords": ["6-8 YouTube search phrases"],
  "character": "one VERY detailed English sentence about the kitten's exact appearance AND the setting",
  "scenes": [
    {{
      "base_visual": "English: main frozen moment with framing + lighting. 2 sentences.",
      "dialogue": "Roman Hindi/Urdu line, max 8 words",
      "sfx": "short sound effect description",
      "motions": ["motion frame 1", "motion frame 2", ... {frames_per_scene} items total]
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
        if not scene.get("base_visual") or not scene.get("dialogue"):
            return False
        motions = scene.get("motions")
        if not isinstance(motions, list) or len(motions) < frames_per_scene:
            # Pad if short
            scene["motions"] = (motions or []) + [
                "same pose, tiny change"] * frames_per_scene
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
    # Add fake motions for fallback
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
    base = scene.get("base_visual", "")
    motions = scene.get("motions", [])
    motion = motions[frame_index % len(motions)] if motions else ""

    # Emphasize consistency
    prompt = f"""
{STYLE}

CHARACTER (must match EXACTLY in every frame):
{character}

SCENE (base composition):
{base}

FRAME {frame_index + 1} of {total_frames}:
Tiny pose change from previous frame: {motion}

IMPORTANT:
- Character must look IDENTICAL to all other frames (same fur, eyes, color)
- Only the POSE changes slightly
- Same camera angle, same lighting, same background
- Face FRONT-FACING, centered, well lit

NEGATIVE: {NEGATIVE}
"""
    return " ".join(prompt.split())


def scene_dialogue(story, index):
    scenes = story.get("scenes", [])
    if not scenes:
        return ""
    return scenes[index % len(scenes)].get("dialogue", "")


def scene_sfx(story, index):
    scenes = story.get("scenes", [])
    if not scenes:
        return ""
    return scenes[index % len(scenes)].get("sfx", "light gentle sound effect")
