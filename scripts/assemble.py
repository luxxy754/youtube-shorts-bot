"""ffmpeg: subtle motion (breathing + head bob + arm sway) + concat + audio mix.

Motion technique:
  1. Breathing pulse: whole image zooms 1% sinusoidally
  2. Head bob: top 40% of image is nudged horizontally ~4px in a slow wave
  3. Arm sway: outer 20% strips (left + right) shift vertically ~3px in opposite phase

Result: character feels "alive" without AI video generation.
The mouth area stays stable so Wav2Lip lipsync is not disturbed.
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


def _motion_filter(fps: int = 30) -> str:
    """Build the full FFmpeg -vf chain for one scene.

    Layers (all combined via a single filtergraph):
      - base:      whole image breathing zoom  (1.000 <-> 1.010)
      - head band: top 40% nudged horizontally +/-4px at slow speed
      - left arm:  leftmost 22% strip shifted vertically +/-3px
      - right arm: rightmost 22% strip shifted vertically -/+3px (opposite)
    """
    # Breathing: zoom oscillates over ~90 frames (3s at 30fps)
    # z = 1.005 + 0.005*sin(on/45)  ->  range 1.000 .. 1.010
    return (
        # 1) Normalize input size first
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        # 2) Split into base, head, left arm, right arm
        "split=4[base][head][larm][rarm];"

        # 3) BASE: breathing zoom
        "[base]zoompan="
        "z='1.005+0.005*sin(on/45)':"
        "x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':"
        f"d=1:s=1080x1920:fps={fps},"
        "setsar=1[basez];"

        # 4) HEAD BAND: top 40%, slight horizontal nudge
        "[head]crop=1080:768:0:0[headc];"
        "[headc]crop=1080:768:0:0,"
        "pad=1180:768:50:0:color=black@0[headp];"
        # shift the padded head crop left/right by +/-4px using overlay x expression
        # We'll re-overlay it on basez later with x expression = (W-w)/2 + 4*sin(t*2)

        # 5) LEFT ARM: leftmost 22% strip, vertical nudge
        "[larm]crop=238:1920:0:0[larmc];"

        # 6) RIGHT ARM: rightmost 22% strip, vertical nudge (opposite phase)
        "[rarm]crop=238:1920:842:0[rarmc];"

        # 7) Compose: base -> overlay head -> overlay left arm -> overlay right arm
        "[basez][headp]overlay="
        "x='(W-w)/2+4*sin(t*2)':"
        "y=0:shortest=1[withhead];"

        "[withhead][larmc]overlay="
        "x=0:"
        "y='3*sin(t*2+0.5)':"
        "shortest=1[withlarm];"

        "[withlarm][rarmc]overlay="
        "x=842:"
        "y='-3*sin(t*2+0.5)':"
        "shortest=1[final];"

        "[final]format=yuv420p"
    )


def apply_motion(input_video: str, output_video: str) -> bool:
    """Wrap one scene video with breathing + head bob + arm sway."""
    try:
        _run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", input_video,
            "-vf", _motion_filter(),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "copy",
            "-movflags", "+faststart",
            output_video,
        ])
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  Motion filter failed: {str(exc)[:200]}")
        return False


def join_clips(clips, out_dir):
    """clips: list of scene video paths. Returns (joined_video, [durations])."""
    norm, durs = [], []
    for i, c in enumerate(clips):
        n = os.path.join(out_dir, f"norm_{i}.mp4")
        if apply_motion(c, n):
            norm.append(n)
        else:
            norm.append(c)
        durs.append(_duration(norm[-1]))

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
    """SFX on top, music ducked. Preserves dialogue from joined track."""
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

    filters.append(f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo,"
                   f"volume=1.0[dlg]")

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
        filters.append("[dlg][sfxout][musd]amix=inputs=3:normalize=0:duration=longest[pre]")
    elif has_sfx:
        filters.append("[dlg][sfxpad]amix=inputs=2:normalize=0:duration=longest[pre]")
    elif has_music:
        filters.append("[dlg][mus]amix=inputs=2:normalize=0:duration=longest[pre]")
    else:
        filters.append("[dlg]anull[pre]")

    filters.append("[pre]loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.95[a]")

    cmd += ["-filter_complex", ";".join(filters),
            "-map", "0:v", "-map", "[a]",
            "-t", f"{total:.2f}",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-ar", "44100", "-movflags", "+faststart", output]
    _run(cmd)
