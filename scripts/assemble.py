"""ffmpeg: frames -> animation, blink, breathing, concat, audio mix."""
import os
import subprocess


def _run(cmd):
    subprocess.run(cmd, check=True)


def _duration(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nk=1:nw=1", path], text=True)
    return float(out.strip())


def frames_to_video(frames, out_path, fps=8):
    """Combine frames into a choppy animation video.

    fps=8 gives classic cartoon feel.
    Each frame is held for 1/fps seconds, creating the animation effect.
    """
    if not frames:
        return False
    # Build filter: concat all frames
    lst = out_path + ".txt"
    with open(lst, "w") as f:
        for fp in frames:
            # Each frame held for 1/fps sec
            f.write(f"file '{os.path.abspath(fp)}'\n")
            f.write(f"duration {1.0 / fps}\n")
        # Repeat last frame once more (ffmpeg requirement)
        f.write(f"file '{os.path.abspath(frames[-1])}'\n")

    try:
        _run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", lst,
            "-vf", f"fps={fps},scale=1080:1920:force_original_aspect_ratio=decrease,"
                   f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            out_path,
        ])
        os.remove(lst)
        return True
    except Exception as exc:
        print(f"  frames_to_video fail: {str(exc)[:200]}")
        return False


def add_blink(video_path, blink_image, out_path):
    """Overlay blink image every ~2.5 seconds for a natural blink."""
    try:
        dur = _duration(video_path)
        blink_interval = 2.5
        blink_dur = 0.05
        n_blinks = max(1, int(dur / blink_interval))
        enable_expr = "+".join(
            f"between(t,{i*blink_interval},{i*blink_interval + blink_dur})"
            for i in range(1, n_blinks + 1)
        )
        _run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", video_path,
            "-i", blink_image,
            "-filter_complex",
            f"[1:v]scale=1080:1920[blink];"
            f"[0:v][blink]overlay=0:0:enable='{enable_expr}'[out]",
            "-map", "[out]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "copy",
            "-movflags", "+faststart",
            out_path,
        ], timeout=300)
        return True
    except Exception as exc:
        print(f"  add_blink fail: {str(exc)[:200]}")
        import shutil
        shutil.copy(video_path, out_path)
        return False


def apply_breathing(input_video, output_video, fps=30):
    """Subtle breathing zoom."""
    try:
        _run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", input_video,
            "-vf", (
                "scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,"
                "zoompan=z='1.005+0.005*sin(on/45)':"
                "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d=1:s=1080x1920:fps={fps},"
                "setsar=1,format=yuv420p"
            ),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "copy",
            "-movflags", "+faststart",
            output_video,
        ])
        return True
    except Exception as exc:
        print(f"  breathing fail: {str(exc)[:200]}")
        return False


def join_clips(clips, out_dir):
    """Concatenate scene videos."""
    lst = os.path.join(out_dir, "list.txt")
    with open(lst, "w") as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c)}'\n")
    joined = os.path.join(out_dir, "joined.mp4")
    _run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", lst,
        "-c", "copy", joined,
    ])
    durs = [_duration(c) for c in clips]
    return joined, durs


def mix(joined, durs, sfx, music, output, music_volume=0.16, sfx_volume=0.85):
    """Mix SFX + ducked music + dialogue."""
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
  
