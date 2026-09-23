"""Story generator for 'Talking Vegetables' Hindi/Urdu Shorts.

Each scene has:
  - visual:   Pixar-style image description
  - dialogue: short Hindi/Urdu line the vegetable speaks (kids-friendly)
  - sfx:      short sound effect description

Dialogue rules: 3-8 simple words, Roman Hindi/Urdu, no difficult words.
"""
import json
import os
import random
import re

import requests


THEMES = [
    "tomato aur aalu dhoop mein jagah share karna seekhte hain",
    "chota matar bade kaddu se dosti karna chahta hai",
    "gajar bazaar mein kho jata hai, pyaaz uski madad karta hai",
    "broccoli seekhta hai ke hara hona special hai",
    "mirchi apna gussa control karna seekhti hai",
    "kheera aur tamatar makkai ke liye surprise party plan karte hain",
    "chota aalu pehli baar zameen ke neeche ja kar bahadur banta hai",
    "nimbu aur mosambi dosti ka maza lete hain",
    "baingan apna purple rang pasand karna seekhta hai",
    "lehsun aur adrak achhe dost ban jate hain",
]

STYLE = (
    "Pixar-style 3D animated movie still, cinematic quality, "
    "cute stylized vegetables with big expressive cartoon eyes and small smiling mouths, "
    "soft rounded shapes, warm detailed faces, stubby arms and legs, "
    "bright cheerful colors, warm golden-hour lighting, "
    "shallow depth of field with soft bokeh background, "
    "simple clean background (sunny garden, kitchen counter, market stall), "
    "vertical 9:16 composition, FRONT-FACING character centered in frame, "
    "face clearly visible and well lit, looking at camera, "
    "absolutely no text, no subtitles, no watermark, no logo, "
    "no humans, no scary elements, no violence, "
    "no 2D illustration, no anime, no sketch, no realistic photorealism"
)

FALLBACK = {
    "title": "Tamatar aur Aalu ki Dosti 🍅🥔 #shorts",
    "description": "Ek chota tamatar aur ek sust aalu dhoop mein dosti karte hain.",
    "hashtags": ["#vegetables", "#cute", "#animation", "#shorts", "#kids", "#hindi"],
    "keywords": ["cute vegetable animation", "hindi kids story", "talking vegetables", "3d cartoon"],
    "character": (
        "a tiny round red tomato with big shiny black cartoon eyes, small green leaf on top, "
        "cute stubby arms and small legs, smiling small mouth; "
        "standing next to a chubby brown potato with sleepy half-closed eyes and lazy smile, "
        "small stubby arms, sitting on soft brown soil in a sunny vegetable garden"
    ),
    "scenes": [
        {
            "visual": "The tiny red tomato stands next to the chubby potato on a sunny garden patch, looking up at him with wide hopeful eyes, small smile. Medium shot, eye-level, front-facing, warm morning sunlight.",
            "dialogue": "Aalu bhai, dhoop mein saath baithen?",
            "sfx": "soft hopeful chirp"
        },
        {
            "visual": "The chubby potato turns slightly away with a lazy grumpy face, eyes half closed, arms folded. Wide shot, front-facing, soft afternoon shadow.",
            "dialogue": "Nahi, mujhe neend aa rahi hai.",
            "sfx": "grumpy mumble"
        },
        {
            "visual": "The tiny tomato holds out a small green leaf like a gift, big sparkly eyes, warm smile. Close-up, front-facing, gentle golden light.",
            "dialogue": "Yeh patta tumhare liye laaya hoon!",
            "sfx": "sweet sparkle sound"
        },
        {
            "visual": "The potato smiles warmly and gently hugs the tomato, both looking happy and cozy. Medium shot, front-facing, golden hour light.",
            "dialogue": "Shukriya dost, tum achhe ho!",
            "sfx": "happy giggle and warm chime"
        },
    ],
    "music": "playful cinematic instrumental with ukulele, marimba, light drums, no vocals",
}


def _prompt(n_scenes):
    theme = random.choice(THEMES)
    return f"""
You are writing a SHORT, kids-friendly YouTube Shorts story about
TALKING VEGETABLES in Pixar 3D style.

TARGET AUDIENCE: 3-6 year old Hindi/Urdu speaking children.
LANGUAGE: Roman Hindi/Urdu (like "Aalu bhai, kaisay ho?").
Use ONLY very simple, everyday words. NO difficult or formal words.

THEME: {theme}

Each scene has THREE parts:
  1. "visual":   ONE frozen moment - vegetable subject, expression, pose,
                 camera framing (front-facing, face centered), lighting.
                 This will be sent to an IMAGE generator.
  2. "dialogue": ONE very short Hindi/Urdu line spoken by a vegetable.
                 Max 8 words. Simple. Funny. Kid-friendly.
                 Use Roman script (e.g. "Yeh kya hai?", "Main bhookha hoon!").
  3. "sfx":      short non-verbal sound effect (chirp, thud, giggle, etc.)

CRITICAL RULES:
- Only vegetables as characters. No humans.
- Family friendly. No violence, no horror, no scary elements.
- Character appearance MUST stay identical across all scenes.
- Simple clean background (garden, kitchen, market).
- Dialogue must be understandable by a 4-year-old.
- No difficult Urdu/Hindi words. No English words in dialogue.

Return ONLY valid JSON:

{{
  "title": "warm curiosity-driven Hindi/Urdu title under 80 chars ending with #shorts",
  "description": "one or two short Hindi/Urdu sentences",
  "hashtags": ["#vegetables", "#cute", "#animation", "#shorts", "#kids", "#hindi"],
  "keywords": ["6-8 YouTube search phrases"],
  "character": "one detailed English sentence describing the EXACT appearance of every main vegetable (color, shape, eyes, mouth, arms) AND the setting",
  "scenes": [
    {{
      "visual": "English: ONE frozen moment with framing + lighting. 2-3 sentences.",
      "dialogue": "Roman Hindi/Urdu line, max 8 words",
      "sfx": "short sound effect description in English"
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
        if not isinstance(scene, dict):
            return False
        if not scene.get("visual") or not scene.get("dialogue"):
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
    """Image-generation prompt for one scene."""
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

Shot {index + 1}. The vegetable appearance must match previous shots EXACTLY.
Face must be FRONT-FACING, centered, clearly visible for lip-sync.

NEGATIVE: text, watermark, logo, human, extra limbs, extra eyes,
distorted face, deformed mouth, cropped head, 2D drawing, anime,
sketch, blurry, scary, dark, violence.
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
