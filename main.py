"""Talking Vegetables Shorts: story -> images -> dialogue -> lipsync -> motion -> upload."""
import json
import os
import random

from scripts.assemble import join_clips, mix
from scripts.audio import eleven_dialogue, get_music, get_sfx, music_credit
from scripts.story import generate_story, scene_dialogue, scene_prompt, scene_sfx
from scripts.upload_youtube import have_credentials, upload_to_youtube
from scripts.video import (
    pollinations_image,
    static_video,
    wav2lip_sync,
)

OUT = "output"
NUM_SCENES = int(os.getenv("NUM_SCENES", "4"))
MUSIC_VOLUME = float(os.getenv("MUSIC_VOLUME", "0.16"))


def build_metadata(story, credit=None):
    tags = [h.lstrip("#") for h in story.get("
