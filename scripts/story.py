"""Story idea generator: Gemini first, Groq second, built-in story last."""
import json
import os
import random
import re

import requests

THEMES = [
    "a cute cat takes a duck for a motorcycle ride",
    "a cute cat tries to sneak a baby chick into a fancy hat shop",
    "a cute cat and a puppy race tiny go-karts",
    "a cute cat pretends to be a chef and a hamster is the customer",
    "a cute cat drives a tiny taxi with a penguin passenger",
    "a cute cat and a bunny try to steal a giant fish from a kitchen",
    "a cute cat teaches a baby duck how to skateboard",
]

STYLE = (
    "3D Pixar style animation, cute expressive animal characters, vibrant colors, "
    "soft cinematic lighting, smooth natural motion, vertical 9:16 framing, "
    "no text, no subtitles, no dialogue"
)

FALLBACK = {
    "title": "Never Trust A Cat! 🐱🏍️ #shorts #cat #funny",
    "description": "The ultimate betrayal! Watch what happens when a cute cat takes a duck for a ride...",
    "hashtags": ["#cat", "#funny", "#3danimation", "#pixar", "#viral", "#shorts", "#funnyanimals"],
    "keywords": ["funny cat video", "3D animation shorts", "cat and duck", "cute animal animation", "viral shorts"],
    "character": (
        "a fluffy orange tabby cat wearing a small red helmet and a small yellow duckling "
        "with big eyes, in a sunny cartoon village"
    ),
    "scenes": [
        {"visual": "the friendly cat waves at the duckling and pats the seat of a small red motorcycle, smiling warmly",
         "sfx": "cute cat meow"},
        {"visual": "the cat and the duckling ride the motorcycle down a sunny road, wind in their fur and feathers",
         "sfx": "small motorcycle engine revving and driving"},
        {"visual": "the cat stops in front of a giant cooking pot and puts on a chef hat with a sneaky grin while the duckling gasps",
         "sfx": "duck quack panicked, then sneaky cat laugh"},
    ],
    "music": "playful cheerful ukulele and pizzicato cartoon background music, instrumental, light and funny",
}


def _prompt(n_scenes):
    theme = random.choice(THEMES)
    return f"""Create ONE funny viral YouTube Short idea, 3D animated Pixar-style, about: {theme}.
It has NO speech and NO voiceover. It is told only through visuals, sound effects and music.
Structure: {n_scenes} scenes of ~5 seconds each: friendly setup, fun moment, surprising funny twist at the end.
Keep it family friendly, no violence, no gore, no text on screen.
Return ONLY JSON with exactly these keys:
{{
 "title": "curiosity title under 80 chars with 1-2 emojis and ending with #shorts",
 "description": "1-2 short engaging sentences",
 "hashtags": ["#cat", "... 6-8 hashtags incl. #shorts"],
 "keywords": ["6-8 search keyword phrases people would search on YouTube"],
 "character": "one detailed sentence describing the exact look of the main characters (colors, clothes, size), reused in every scene for consistency",
 "scenes": [{{"visual": "what happens, one sentence, concrete action and camera", "sfx": "short sound effect description e.g. cat meow"}}],
 "music": "short description of funny background music"
}}
The scenes array must have exactly {n_scenes} items."""


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
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0}},
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
        json={"model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
              "messages": [{"role": "user", "content": prompt}],
              "response_format": {"type": "json_object"}, "temperature": 1.0},
        timeout=90,
    )
    r.raise_for_status()
    return json.loads(_clean(r.json()["choices"][0]["message"]["content"]))


def _valid(s, n):
    return (isinstance(s, dict) and s.get("title") and s.get("character")
            and isinstance(s.get("scenes"), list) and len(s["scenes"]) >= 1
            and all(isinstance(x, dict) and x.get("visual") for x in s["scenes"]))


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
    return f"{STYLE}. Characters: {story['character']}. Scene: {scene['visual']}."
