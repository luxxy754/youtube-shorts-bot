"""Pet Drama story generator - Hindi/Urdu, dramatic, kids-friendly."""
import json
import os
import random
import re

import requests


THEMES = [
    "ek billi apne dost ko dhoka deti hai aur baad mein pachtati hai",
    "ek puppy apni maa ki baat nahi maanta aur mushkil mein phas jata hai",
    "do billiyan ek gend ke liye ladti hain, phir dosti karti hain",
    "ek billi apne ghar se bhaag jati hai aur wapas aana chahti hai",
    "ek puppy apne bhai ke saath khana share karna seekhta hai",
    "ek billi apni behen se jealous hoti hai phir maafi mangti hai",
    "ek chota puppy pehli baar barish dekhta hai aur darta hai",
    "do dost billiyan ek saath kho jati hain aur raasta dhoondti hain",
    "ek billi apne maalik ki nayi billi se dosti karti hai",
    "ek puppy apni favorite toy khone par udaas hota hai",
    "ek billi ko pata chalta hai ke uska dost bimar hai",
    "do puppies ek hi khilona share karna seekhte hain",
]

# ---- REALISTIC Pixar style ----
STYLE = (
    "Photorealistic 3D render in the style of a Pixar movie, "
    "extremely cute cat or dog character, "
    "highly detailed realistic fur with individual strands visible, "
    "realistic eye reflections and moist nose, "
    "soft skin texture with subsurface scattering, "
    "professional cinematic studio lighting, "
    "shallow depth of field with creamy bokeh, "
    "warm golden color grading, "
    "shot on Canon EOS R5 with 85mm lens at f/1.8, "
    "ray-traced soft shadows, ambient occlusion, "
    "volumetric light with dust particles, "
    "8K hyper-detailed texture, "
    "vertical 9:16 portrait composition, "
    "front-facing character centered in frame, face clearly visible and well lit, "
    "expressive BIG glossy eyes showing clear emotion, "
    "absolutely no text, no subtitles, no watermark, no logo, "
    "no humans, no scary elements, no violence, "
    "no 2D illustration, no anime, no sketch, no cartoon flat colors"
)

NEGATIVE = (
    "blurry, low quality, low resolution, jpeg artifacts, "
    "cartoon, flat colors, plasticky, waxy, doll-like, "
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
    "title": "Billi ki Naarazgi, Phir Pyaar! 🐱❤️ #shorts",
    "description": "Ek billi apne dost se naraz hai, lekin pyaar jeet jata hai.",
    "hashtags": ["#cat", "#dog", "#pets", "#cute", "#drama", "#shorts", "#kids"],
    "keywords": ["cute pet drama", "cat dog story", "pet animation", "kids story"],
    "character": (
        "a tiny fluffy orange tabby kitten with BIG glossy expressive eyes, "
        "small pink nose, chubby soft realistic fur body, tiny paws, "
        "standing next to a small brown puppy with big sad eyes and floppy ears, "
        "in a warm cozy living room with wooden floor and soft rug, "
        "sunlight coming through a window"
    ),
    "scenes": [
        {
            "visual": "The tiny orange kitten looks at the puppy with sad watery eyes, sitting apart. Medium shot, front-facing, warm morning light through window.",
            "dialogue": "Tumne mujhe dhoka diya!",
            "sfx": "sad soft meow"
        },
        {
            "visual": "The puppy turns away with angry face, ears down. Close-up, front-facing, soft shadows.",
            "dialogue": "Main tumse naraz hoon!",
            "sfx": "angry puppy whimper"
        },
        {
            "visual": "The kitten holds out a small toy as a gift, hopeful eyes, small smile. Close-up, front-facing, warm golden light.",
            "dialogue": "Yeh lo, meri dost ban jao!",
            "sfx": "hopeful chirp"
        },
        {
            "visual": "The puppy and kitten hug happily, both smiling big with sparkling eyes. Medium shot, front-facing, warm golden hour light.",
            "dialogue": "Hum hamesha dost rahenge!",
            "sfx": "happy bark and purr"
        },
    ],
    "music": "playful cinematic instrumental with ukulele, marimba, light drums, no vocals",
}


def _prompt(n_scenes):
    theme = random.choice(THEMES)
    return f"""
You are writing a SHORT, dramatic YouTube Shorts story about PETS
(cats and dogs) in Pixar 3D realistic style.

TARGET AUDIENCE: kids and young adults in Pakistan/India.
LANGUAGE: Roman Hindi/Urdu (like "Tumne mujhe kyun chhoda?").
Use ONLY simple everyday words. NO difficult words.

THEME: {theme}

Each scene has 3 parts:
  1. "visual": English description of ONE frozen moment - pose,
                expression, framing, lighting. Front-facing.
                Use vivid words: glossy eyes, detailed fur, warm light,
                cinematic, bokeh.
  2. "dialogue": ONE short Hindi/Urdu line (max 8 words) - dramatic!
                 Should sound emotional. Roman script.
  3. "sfx": short animal sound (meow, bark, whimper, etc.)

CRITICAL:
- Only cats/dogs as characters. No humans.
- Family friendly. No violence, no scary elements.
- Pet appearance MUST stay identical across all scenes.
- Dramatic emotions: sad, angry, happy, hopeful.
- Dialogue should be emotional, not flat.

Return ONLY valid JSON:

{{
  "title": "dramatic Hindi/Urdu title under 80 chars ending with #shorts",
  "description": "one or two short Hindi/Urdu sentences",
  "hashtags": ["#cat", "#dog", "#pets", "#cute", "#drama", "#shorts", "#kids"],
  "keywords": ["6-8 YouTube search phrases"],
  "character": "one VERY detailed English sentence about the pets' appearance AND setting",
  "scenes": [
    {{
      "visual": "English: ONE frozen moment with framing + lighting. 2 sentences.",
      "dialogue": "Roman Hindi/Urdu line, max 8 words, emotional",
      "sfx": "short animal sound description"
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
                                    "temperature": 1.1}},
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
              "temperature": 1.1},
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
    scenes = story.get("scenes", [])
    if not scenes:
        return ""
    scene = scenes[index % len(scenes)]
    character = story.get("character", "")
    visual = scene.get("visual", "")

    prompt = f"""
{STYLE}

CHARACTER (must match EXACTLY in every image):
{character}

THIS SCENE:
{visual}

Shot {index + 1}. The pet must look IDENTICAL to other frames.
Face FRONT-FACING, centered, well lit.

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
    return scenes[index % len(scenes)].get("sfx", "cute pet sound")
