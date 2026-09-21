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

# Render-engine wording matters far more than the words "Pixar style".
# Model needs to be told it is looking at a RENDER, not a drawing.
STYLE = (
    "3D CGI animated short film, Pixar / DreamWorks feature film quality, semi-realistic "
    "creature design (natural animal body proportions, not exaggerated toy-like big-head "
    "cartoon proportions), realistic detailed fur and skin texture, "
    "Unreal Engine 5 cinematic render, octane render, subsurface scattering on skin, "
    "physically based rendering, ray traced global illumination, soft volumetric light, "
    "shallow depth of field, detailed fur simulation with individual strands, "
    "glossy expressive realistic eyes with catchlights and reflections, "
    "vibrant natural colour grading, "
    "smooth fluid character animation with clear body acting, "
    "medium shot, both characters fully inside frame with headroom and margin on both sides, "
    "nothing touching or cropped by the frame edges, centred composition, "
    "vertical 9:16 portrait framing, full body visible, 24fps cinematic motion, "
    "NOT flat 2D, not a drawing, not an illustration, not anime, not a cartoon sketch, "
    "no text, no watermark, no subtitles, no dialogue, no human characters"
)

FALLBACK = {
    "title": "Never Trust A Cat! 🐱🏍️ #shorts",
    "description": "The ultimate betrayal! Watch what happens when a cute cat takes a duck for a ride...",
    "hashtags": ["#cat", "#funny", "#3danimation", "#pixar", "#viral", "#shorts", "#funnyanimals"],
    "keywords": ["funny cat video", "3D animation shorts", "cat and duck",
                 "cute animal animation", "viral shorts"],
    "character": (
        "a chubby fluffy orange tabby cat with huge round green eyes, white chest fur and a tiny "
        "red crash helmet, and a small round yellow duckling with an orange beak and big shiny "
        "black eyes, in a sunny colourful cartoon village with pastel houses"
    ),
    "scenes": [
        {"visual": "the orange cat grins and pats the seat of a small red motorcycle, the yellow "
                   "duckling waddles up excitedly and hops on, camera slowly pushes in on them",
         "sfx": "cute cat meow and a small happy duck quack"},
        {"visual": "the cat and the duckling speed down a sunny village road on the red motorcycle, "
                   "fur and feathers blowing back, camera tracks alongside them at low angle",
         "sfx": "small motorcycle engine revving and driving fast"},
        {"visual": "the motorcycle screeches to a stop in front of a giant steaming cooking pot, the "
                   "cat slowly puts on a white chef hat with a sneaky grin, camera pushes in fast on "
                   "the duckling's shocked wide-eyed face",
         "sfx": "tyre screech then a panicked duck quack"},
    ],
    "music": "playful cheerful upbeat cartoon score, ukulele, pizzicato strings, marimba and light "
             "percussion, comedic and bouncy, instrumental only, no vocals",
}


def _prompt(n_scenes):
    theme = random.choice(THEMES)
    return f"""Create ONE funny viral YouTube Short idea, 3D CGI Pixar-style animation, about: {theme}.
It has NO speech and NO voiceover. It is told only through visuals, sound effects and music.
Structure: {n_scenes} scenes of ~5 seconds each: friendly setup, fun moment, surprising funny twist at the end.
Keep it family friendly, no violence, no gore, no text on screen, no human characters.

IMPORTANT for each scene "visual":
- Describe ONE continuous 5 second shot, present tense.
- Always name the characters by their colour/look (e.g. "the orange tabby cat"), never "he"/"it".
- Include one clear physical ACTION and one CAMERA move (push in, track alongside, low angle, slow orbit).
- Include a readable facial expression (grinning, shocked wide eyes, proud smirk).
- Do NOT mention style, render or "3D" - that is added separately.

Return ONLY JSON with exactly these keys:
{{
 "title": "curiosity title under 80 chars with 1-2 emojis and ending with #shorts",
 "description": "1-2 short engaging sentences",
 "hashtags": ["#cat", "... 6-8 hashtags incl. #shorts"],
 "keywords": ["6-8 search keyword phrases people would search on YouTube"],
 "character": "ONE detailed sentence describing the exact look of the main characters - species, body shape, fur/feather colour, eye colour, clothing, size difference, and the setting. This exact sentence is reused in every scene for consistency, so be very specific.",
 "scenes": [{{"visual": "one sentence, concrete action + camera + expression", "sfx": "short sound effect description e.g. cat meow"}}],
 "music": "short description of funny instrumental background music, name real instruments and tempo"
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
    """Character description FIRST - video models weight the start of the prompt most."""
    return (f"{story['character']}. {scene['visual']}. {STYLE}.")
