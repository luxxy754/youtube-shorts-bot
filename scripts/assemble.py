"""ffmpeg: normalise clips to 1080x1920, join them, mix sfx + music."""
import os
import subprocess


def _run(cmd):
    subprocess.run(cmd, check=True)


def _duration(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nk=1:nw=1", path], text=True)
    return float(out.strip())


def join_clips(clips, out_dir, max_len):
    """Returns (joined_video_path, [duration per clip])."""
    vf = ("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
          "setsar=1,fps=30,format=yuv420p")
    norm, durs = [], []
    for i, c in enumerate(clips):
        n = os.path.join(out_dir, f"norm_{i}.mp4")
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", c, "-an", "-t", str(max_len),
              "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", n])
        norm.append(n)
        durs.append(_duration(n))
    lst = os.path.join(out_dir, "list.txt")
    with open(lst, "w") as f:
        for n in norm:
            f.write(f"file '{os.path.abspath(n)}'\n")
    joined = os.path.join(out_dir, "joined.mp4")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", lst, "-c", "copy", joined])
    return joined, durs


def mix(joined, durs, sfx, music, output, music_volume=0.16, sfx_volume=0.85):
    """Mix: SFX on top, music underneath and DUCKED whenever an SFX plays,
    then loudness-normalised so nothing is harsh or clipping."""
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
        # pad to full length so the sidechain key covers the whole video
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
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-c", "copy",
              "-movflags", "+faststart", output])
        return

    # This is what stops the "ganda / loud / distorted" sound.
    filters.append("[pre]loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.95[a]")

    cmd += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[a]",
            "-t", f"{total:.2f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-ar", "44100", "-movflags", "+faststart", output]
    _run(cmd)
