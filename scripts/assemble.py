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


def mix(joined, durs, sfx, music, output, music_volume=0.30, sfx_volume=1.0):
    total = sum(durs)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", joined]
    filters, labels, idx = [], [], 1
    start = 0.0
    for d, s in zip(durs, sfx):
        if s:
            cmd += ["-i", s]
            ms = int((start + 0.3) * 1000)
            filters.append(f"[{idx}:a]adelay={ms}|{ms},volume={sfx_volume}[s{idx}]")
            labels.append(f"[s{idx}]")
            idx += 1
        start += d
    if music:
        cmd += ["-stream_loop", "-1", "-i", music]
        fade = max(total - 1.0, 0)
        filters.append(f"[{idx}:a]atrim=0:{total},asetpts=N/SR/TB,volume={music_volume},"
                       f"afade=t=out:st={fade}:d=1[m]")
        labels.append("[m]")
    if not labels:
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-c", "copy",
              "-movflags", "+faststart", output])
        return
    filters.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest[a]")
    cmd += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[a]",
            "-t", f"{total:.2f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", output]
    _run(cmd)
