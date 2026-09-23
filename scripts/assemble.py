"""ffmpeg: turn each scene IMAGE into a motion clip, join, mix sfx + music.

Motion is a "Ken Burns" effect: slowly push in or pull out while panning
slightly, so the still image feels alive. Scene index determines direction
so consecutive scenes have varied motion.
"""
import os
import subprocess


def _run(cmd):
    subprocess.run(cmd, check=True)


def _duration(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nk=1:nw=1", path], text=True)
    return float(out.strip())


# (zoom direction, pan direction) per scene index
_MOTIONS = [
    ("in",  "right"),   # push in + slight pan right
    ("out", "left"),    # pull out + slight pan left
    ("in",  "up"),      # push in + slight pan up
    ("out", "down"),    # pull out + slight pan down
]


def _ken_burns_filter(scene_index: int, seconds: int, fps: int = 30) -> str:
    """Return the ffmpeg -vf chain that turns a still into motion.

    Input is assumed 1080x1920 already (Pollinations generates at that size).
    We scale slightly larger to give zoompan room, then apply zoompan.
    """
    zoom_dir, pan_dir = _MOTIONS[scene_index % len(_MOTIONS)]

    if zoom_dir == "in":
        z_expr = "min(zoom+0.0012,1.25)"
    else:
        z_expr = "max(1.25-0.0012*on,1.0)"

    # panning offsets in normalized units
    if pan_dir == "right":
        x_expr = "iw/2-(iw/zoom/2)+on*0.6"
        y_expr = "ih/2-(ih/zoom/2)"
    elif pan_dir == "left":
        x_expr = "iw/2-(iw/zoom/2)-on*0.6"
        y_expr = "ih/2-(ih/zoom/2)"
    elif pan_dir == "up":
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)-on*0.6"
    else:  # down
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)+on*0.6"

    frames = seconds * fps

    return (
        # scale up slightly (safe area for zoompan), then zoompan, then fit
        "scale=1188:2112:force_original_aspect_ratio=increase,"
        f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}'"
        f":d={frames}:s=1080x1920:fps={fps},"
        "setsar=1,format=yuv420p"
    )


def join_clips(clips, out_dir, max_len):
    """clips: list of IMAGE paths (jpg). Returns (joined_video, [durations]).

    Each image becomes a max_len-second motion clip. Then all clips are
    concatenated into a single 1080x1920 mp4.
    """
    norm, durs = [], []
    for i, img in enumerate(clips):
        n = os.path.join(out_dir, f"norm_{i}.mp4")
        vf = _ken_burns_filter(i, max_len)
        _run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-i", img,
            "-t", str(max_len),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            n,
        ])
        norm.append(n)
        durs.append(_duration(n))

    lst = os.path.join(out_dir, "list.txt")
    with open(lst, "w") as f:
        for n in norm:
            f.write(f"file '{os.path.abspath(n)}'\n")

    joined = os.path.join(out_dir, "joined.mp4")
    _run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", lst,
        "-c", "copy", joined,
    ])
    return joined, durs


def mix(joined, durs, sfx, music, output, music_volume=0.16, sfx_volume=0.85):
    """Mix SFX on top of ducked music, loudness-normalized."""
    total = sum(durs)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", joined]
    filters, sfx_labels, idx = [], [], 1

    start = 0.0
    for d, s in zip(durs, sfx):
        if s:
            cmd += ["-i", s]
            ms = int((start + 0.25) * 1000)
            filters.append(
                f"[{idx}:a]aformat=sample_rates=44100:channel_layouts=stereo,"
                f"adelay={ms}|{ms},volume={sfx_volume}[s{idx}]")
            sfx_labels.append(f"[s{idx}]")
            idx += 1
        start += d

    has_sfx = bool(sfx_labels)
    if has_sfx:
        if len(sfx_labels) > 1:
            filters.append("".join(sfx_labels) +
                           f"amix=inputs={len(sfx_labels)}:normalize=0:duration=longest[sfxraw]")
        else:
            filters.append(f"{sfx_labels[0]}anull[sfxraw]")
        filters.append(f"[sfxraw]apad,atrim=0:{total:.2f},asetpts=N/SR/TB[sfxpad]")

    has_music = bool(music)
    if has_music:
        cmd += ["-stream_loop", "-1", "-i", music]
        fade = max(total - 1.2, 0)
        filters.append(
            f"[{idx}:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"atrim=0:{total:.2f},asetpts=N/SR/TB,volume={music_volume},"
            f"afade=t=in:st=0:d=0.7,afade=t=out:st={fade:.2f}:d=1.2[mus]")

    if has_sfx and has_music:
        filters.append("[sfxpad]asplit=2[sfxout][sfxkey]")
        filters.append("[mus][sfxkey]sidechaincompress="
                       "threshold=0.02:ratio=8:attack=15:release=400:makeup=1[musd]")
        filters.append("[musd][sfxout]amix=inputs=2:normalize=0:duration=longest[pre]")
    elif has_sfx:
        filters.append("[sfxpad]anull[pre]")
    elif has_music:
        filters.append("[mus]anull[pre]")
    else:
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined,
              "-c", "copy", "-movflags", "+faststart", output])
        return

    filters.append("[pre]loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.95[a]")

    cmd += ["-filter_complex", ";".join(filters),
            "-map", "0:v", "-map", "[a]",
            "-t", f"{total:.2f}",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-ar", "44100", "-movflags", "+faststart", output]
    _run(cmd)
