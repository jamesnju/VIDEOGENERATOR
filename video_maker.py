
from pathlib import Path
import json
import random
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from voice_generator import generate_speech, save_reference


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
VOICE_DIR = BASE_DIR / "generated_voice"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
VOICE_DIR.mkdir(parents=True, exist_ok=True)

FPS = 30

# FFmpeg xfade transition names.
TRANSITIONS = {
    "Cut": "fade",
    "Fade": "fade",
    "Dissolve": "dissolve",
    "Wipe Left": "wipeleft",
    "Wipe Right": "wiperight",
    "Slide Left": "slideleft",
    "Slide Right": "slideright",
    "Smooth Left": "smoothleft",
    "Smooth Right": "smoothright",
    "Zoom In": "zoomin",
    "Circle Open": "circleopen",
    "Circle Close": "circleclose",
    "Fade Through Black": "fadeblack",
    "Fade Through White": "fadewhite",
    "Pixelize": "pixelize",
}

RANDOM_TRANSITIONS = [
    "Fade",
    "Dissolve",
    "Wipe Left",
    "Wipe Right",
    "Slide Left",
    "Slide Right",
    "Zoom In",
    "Fade Through Black",
]


def run_command(command: list[str]) -> None:
    """Run FFmpeg or FFprobe and show a useful error if it fails."""
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError(
            "A video/audio processing command failed.\n\n"
            + result.stderr[-5000:]
        )


def check_tools() -> None:
    """Check that FFmpeg and FFprobe are installed and on PATH."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError(
            "FFmpeg was not found. Install FFmpeg and add its bin folder "
            "to your Windows PATH, then restart Command Prompt."
        )


def get_media_duration(path: str | Path) -> float:
    """Read audio/video duration in seconds using FFprobe."""
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not read media duration: {path}")

    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError(f"Invalid media duration: {path}") from exc


def get_font(size: int) -> ImageFont.ImageFont:
    """Use a readable font, with a fallback if Arial is unavailable."""
    for font_name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(font_name, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    """Wrap subtitles into lines that fit the video."""
    words = text.split()
    lines = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()
        left, top, right, bottom = draw.textbbox(
            (0, 0), candidate, font=font
        )

        if right - left <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def make_scene_image(
    image_path: str,
    narration: str,
    output_path: Path,
    width: int,
    height: int,
    show_subtitles: bool,
) -> None:
    """
    Fit the complete source image over a blurred background.
    The source image itself is not cropped.
    """
    with Image.open(image_path) as source:
        original = source.convert("RGB")

    # Create a blurred, filled background so no black bars are needed.
    background = Image.new("RGB", (width, height), (18, 18, 18))
    cover_scale = max(width / original.width, height / original.height)
    background_size = (
        max(width, int(original.width * cover_scale)),
        max(height, int(original.height * cover_scale)),
    )

    blurred = original.resize(
        background_size, Image.Resampling.LANCZOS
    ).filter(ImageFilter.GaussianBlur(radius=max(12, width // 70)))

    left = (blurred.width - width) // 2
    top = (blurred.height - height) // 2
    background.paste(
        blurred.crop((left, top, left + width, top + height)),
        (0, 0),
    )

    # Fit the whole original image inside the frame.
    foreground = original.copy()
    foreground.thumbnail(
        (int(width * 0.96), int(height * 0.94)),
        Image.Resampling.LANCZOS,
    )
    x = (width - foreground.width) // 2
    y = (height - foreground.height) // 2
    background.paste(foreground, (x, y))

    if show_subtitles and narration.strip():
        draw = ImageDraw.Draw(background)
        font = get_font(max(28, width // 30))
        max_text_width = int(width * 0.86)
        lines = wrap_text(
            draw, narration.strip(), font, max_text_width
        )

        # Limit subtitle height so the text remains inside the frame.
        max_lines = 5
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip(" .") + "…"

        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font, stroke_width=1)
            line_heights.append(max(1, bbox[3] - bbox[1]))

        padding = max(18, width // 60)
        gap = max(8, width // 120)
        text_height = sum(line_heights) + gap * max(0, len(lines) - 1)
        panel_height = text_height + padding * 2
        panel_top = height - panel_height - int(height * 0.035)

        draw.rounded_rectangle(
            (
                int(width * 0.04),
                panel_top,
                int(width * 0.96),
                panel_top + panel_height,
            ),
            radius=max(12, width // 60),
            fill=(0, 0, 0, 220),
        )

        # Draw on a separate transparent layer for panel transparency.
        panel = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.rounded_rectangle(
            (
                int(width * 0.04),
                panel_top,
                int(width * 0.96),
                panel_top + panel_height,
            ),
            radius=max(12, width // 60),
            fill=(0, 0, 0, 205),
        )
        background = Image.alpha_composite(
            background.convert("RGBA"), panel
        ).convert("RGB")

        draw = ImageDraw.Draw(background)
        y_text = panel_top + padding
        for line, line_height in zip(lines, line_heights):
            bbox = draw.textbbox((0, 0), line, font=font, stroke_width=1)
            line_width = bbox[2] - bbox[0]
            x_text = (width - line_width) // 2

            draw.text(
                (x_text, y_text),
                line,
                font=font,
                fill="white",
                stroke_width=2,
                stroke_fill="black",
            )
            y_text += line_height + gap

    background.save(output_path, quality=95)


def create_silent_scene(
    frame_path: Path,
    output_path: Path,
    duration: float,
    width: int,
    height: int,
) -> None:
    """Create a silent MP4 clip from one prepared scene image."""
    run_command([
        "ffmpeg", "-y",
        "-loop", "1",
        "-framerate", str(FPS),
        "-i", str(frame_path),
        "-t", f"{duration:.3f}",
        "-vf", f"scale={width}:{height},fps={FPS},format=yuv420p",
        "-an",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ])


def prepare_audio(
    source_audio: Path,
    output_audio: Path,
    duration: float,
) -> None:
    """Pad short narration with silence to match its scene duration."""
    run_command([
        "ffmpeg", "-y",
        "-i", str(source_audio),
        "-af", "apad",
        "-t", f"{duration:.3f}",
        "-ar", "24000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(output_audio),
    ])


def merge_scenes(
    scene_videos: list[Path],
    scene_audios: list[Path],
    scene_durations: list[float],
    scene_transitions: list[str],
    transition_seconds: float,
    output_path: Path,
) -> None:
    """Join scenes with transitions and join the matching narration tracks."""
    if len(scene_videos) == 1:
        silent_video = scene_videos[0]
        merged_audio = scene_audios[0]
    else:
        # Build the video xfade chain.
        video_inputs = []
        for path in scene_videos:
            video_inputs.extend(["-i", str(path)])

        video_filters = []
        current_video = "[0:v]"
        elapsed = scene_durations[0]

        for index in range(1, len(scene_videos)):
            name = scene_transitions[index]
            xfade_name = TRANSITIONS.get(name, "fade")

            # "Cut" is represented by a near-instant transition.
            overlap = 0.001 if name == "Cut" else transition_seconds
            overlap = min(
                overlap,
                scene_durations[index - 1] * 0.25,
                scene_durations[index] * 0.25,
            )

            next_input = f"[{index}:v]"
            output_label = f"[v{index}]"
            offset = max(0.0, elapsed - overlap)

            video_filters.append(
                f"{current_video}{next_input}"
                f"xfade=transition={xfade_name}:"
                f"duration={overlap:.3f}:offset={offset:.3f}"
                f"{output_label}"
            )

            elapsed = elapsed + scene_durations[index] - overlap
            current_video = output_label

        silent_video = output_path.parent / "merged_silent.mp4"
        run_command([
            "ffmpeg", "-y",
            *video_inputs,
            "-filter_complex", ";".join(video_filters),
            "-map", current_video,
            "-an",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            str(silent_video),
        ])

        # Build a matching audio crossfade chain.
        audio_inputs = []
        for path in scene_audios:
            audio_inputs.extend(["-i", str(path)])

        audio_filters = []
        current_audio = "[0:a]"

        for index in range(1, len(scene_audios)):
            name = scene_transitions[index]
            overlap = 0.001 if name == "Cut" else transition_seconds
            overlap = min(
                overlap,
                scene_durations[index - 1] * 0.25,
                scene_durations[index] * 0.25,
            )

            output_label = f"[a{index}]"
            audio_filters.append(
                f"{current_audio}[{index}:a]"
                f"acrossfade=d={overlap:.3f}:c1=tri:c2=tri"
                f"{output_label}"
            )
            current_audio = output_label

        merged_audio = output_path.parent / "merged_narration.wav"
        run_command([
            "ffmpeg", "-y",
            *audio_inputs,
            "-filter_complex", ";".join(audio_filters),
            "-map", current_audio,
            "-c:a", "pcm_s16le",
            str(merged_audio),
        ])

    # Combine the finished video and narration.
    run_command([
        "ffmpeg", "-y",
        "-i", str(silent_video),
        "-i", str(merged_audio),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        str(output_path),
    ])


def create_video(
    scenes: list[dict],
    reference_upload: str | None = None,
    aspect_ratio: str = "Vertical (9:16)",
    transition_mode: str = "Use scene settings",
    global_transition: str = "Fade",
    transition_seconds: float = 0.5,
    show_subtitles: bool = True,
) -> str:
    """
    Generate a complete video.

    Each scene dictionary:
        image: image file path
        narration: text to speak and optionally display
        duration: minimum scene duration in seconds; 0 means automatic
        transition: transition into this scene
    """
    check_tools()

    # Save the uploaded voice once. If nothing is uploaded, reuse the saved one.
    reference_audio = save_reference(reference_upload)

    if aspect_ratio == "Landscape (16:9)":
        width, height = 1920, 1080
    else:
        width, height = 1080, 1920

    valid_scenes = []
    for index, scene in enumerate(scenes, start=1):
        image_path = scene.get("image")
        narration = (scene.get("narration") or "").strip()

        if not image_path and not narration:
            continue

        if not image_path:
            raise ValueError(f"Scene {index}: please upload an image.")
        if not narration:
            raise ValueError(f"Scene {index}: please enter narration text.")

        if not Path(image_path).is_file():
            raise FileNotFoundError(f"Scene {index}: image file not found.")

        valid_scenes.append({
            "image": image_path,
            "narration": narration,
            "duration": float(scene.get("duration") or 0),
            "transition": scene.get("transition") or "Fade",
        })

    if not valid_scenes:
        raise ValueError("Add at least one scene with an image and narration.")

    # Load/generate all scene audio first so we know the true spoken durations.
    generated_audio = []
    actual_durations = []

    for index, scene in enumerate(valid_scenes, start=1):
        audio_path = VOICE_DIR / f"scene_{index:02d}.wav"

        generate_speech(
            narration_text=scene["narration"],
            reference_audio=reference_audio,
            output_path=str(audio_path),
        )

        speech_duration = get_media_duration(audio_path)

        # A supplied duration is a minimum. Never cut off the spoken words.
        duration = max(scene["duration"], speech_duration + 0.35)
        actual_durations.append(duration)
        generated_audio.append(audio_path)

    output_path = OUTPUT_DIR / "video_output.mp4"

    # Build intermediate clips in a temporary folder.
    with tempfile.TemporaryDirectory(prefix="ai_video_") as temp_name:
        temp_dir = Path(temp_name)
        scene_videos = []
        scene_audios = []

        for index, (scene, audio_path, duration) in enumerate(
            zip(valid_scenes, generated_audio, actual_durations),
            start=1,
        ):
            frame_path = temp_dir / f"scene_{index:02d}.png"
            video_path = temp_dir / f"scene_{index:02d}.mp4"
            padded_audio_path = temp_dir / f"scene_{index:02d}_audio.wav"

            make_scene_image(
                image_path=scene["image"],
                narration=scene["narration"],
                output_path=frame_path,
                width=width,
                height=height,
                show_subtitles=show_subtitles,
            )

            create_silent_scene(
                frame_path=frame_path,
                output_path=video_path,
                duration=duration,
                width=width,
                height=height,
            )

            prepare_audio(
                source_audio=audio_path,
                output_audio=padded_audio_path,
                duration=duration,
            )

            scene_videos.append(video_path)
            scene_audios.append(padded_audio_path)

        # The transition belongs to the scene we are transitioning into.
        transitions = ["Cut"]
        for scene in valid_scenes[1:]:
            if transition_mode == "Random":
                transitions.append(random.choice(RANDOM_TRANSITIONS))
            elif transition_mode == "Same transition for all":
                transitions.append(global_transition)
            else:
                transitions.append(scene["transition"])

        merge_scenes(
            scene_videos=scene_videos,
            scene_audios=scene_audios,
            scene_durations=actual_durations,
            scene_transitions=transitions,
            transition_seconds=float(transition_seconds),
            output_path=output_path,
        )

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Video generation finished without an output file.")

    return str(output_path.resolve())

# import os
# import re
# import shutil
# import subprocess
# import uuid
# import wave
# import random

# import cv2
# import numpy as np
# from PIL import Image, ImageDraw, ImageFont, ImageFilter

# FPS = 20

# # Names shown in the app mapped to FFmpeg's supported transition effects.
# TRANSITIONS = {
#     "Cut": "fade",
#     "Fade": "fade",
#     "Crossfade": "dissolve",
#     "Slide left": "slideleft",
#     "Slide right": "slideright",
#     "Zoom in": "zoomin",
#     "Zoom out": "distance",
#     "Flash": "fadewhite",
#     "Dip to black": "fadeblack",
#     "Dip to white": "fadewhite",
#     "Wipe left": "wipeleft",
#     "Wipe right": "wiperight",
#     "Wipe up": "wipeup",
#     "Wipe down": "wipedown",
#     "Smooth left": "smoothleft",
#     "Smooth right": "smoothright",
#     "Circle open": "circleopen",
#     "Circle close": "circleclose",
#     "Dissolve": "dissolve",
# }

# TRANSITION_NAMES = list(TRANSITIONS.keys())


# def find_ffmpeg():
#     path = shutil.which("ffmpeg")
#     if not path:
#         raise RuntimeError(
#             "FFmpeg was not found. Install FFmpeg, add its bin folder "
#             "to PATH, and restart Command Prompt."
#         )
#     return path


# def get_font(size):
#     candidates = [
#         r"C:\Windows\Fonts\arial.ttf",
#         r"C:\Windows\Fonts\segoeui.ttf",
#         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
#     ]

#     for candidate in candidates:
#         if os.path.exists(candidate):
#             try:
#                 return ImageFont.truetype(candidate, size=size)
#             except OSError:
#                 pass

#     return ImageFont.load_default()


# def audio_duration(path, ffmpeg=None):
#     ffprobe = shutil.which("ffprobe")

#     if ffprobe:
#         result = subprocess.run(
#             [
#                 ffprobe,
#                 "-v", "error",
#                 "-show_entries", "format=duration",
#                 "-of", "default=noprint_wrappers=1:nokey=1",
#                 path,
#             ],
#             capture_output=True,
#             text=True,
#         )

#         if result.returncode == 0:
#             try:
#                 return float(result.stdout.strip())
#             except ValueError:
#                 pass

#     try:
#         with wave.open(path, "rb") as wav:
#             return wav.getnframes() / float(wav.getframerate())
#     except Exception as exc:
#         raise RuntimeError(
#             "Could not read audio duration. Ensure FFmpeg and ffprobe "
#             "are installed and available on PATH."
#         ) from exc


# def split_script(script, max_words=7):
#     words = re.findall(r"\S+", script or "")
#     return [
#         " ".join(words[i:i + max_words])
#         for i in range(0, len(words), max_words)
#     ] or [""]


# def wrap_text(draw, text, font, max_width):
#     words = text.split()
#     lines = []
#     current = ""

#     for word in words:
#         test = word if not current else current + " " + word

#         if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
#             current = test
#         else:
#             if current:
#                 lines.append(current)
#             current = word

#     if current:
#         lines.append(current)

#     return lines


# def make_caption_frame(
#     base,
#     caption,
#     progress,
#     zoom_effect,
#     width,
#     height,
# ):
#     """
#     Keep the complete original image visible.

#     A blurred, canvas-filling copy of the image becomes the background.
#     The original image is fitted inside the canvas without cropping.
#     When zoom is enabled, only the background zooms.
#     """

#     base = base.convert("RGB")

#     # Create a blurred background that fills the whole video canvas.
#     background_scale = max(width / base.width, height / base.height)
#     bg_width = max(width, int(base.width * background_scale))
#     bg_height = max(height, int(base.height * background_scale))

#     background = base.resize(
#         (bg_width, bg_height),
#         Image.Resampling.LANCZOS,
#     )

#     left = max(0, (background.width - width) // 2)
#     top = max(0, (background.height - height) // 2)

#     background = background.crop(
#         (left, top, left + width, top + height)
#     )

#     # Zoom only the blurred background.
#     if zoom_effect:
#         progress = max(0.0, min(1.0, progress))
#         zoom = 1.0 + (0.07 * progress)

#         zoom_width = max(width, int(width * zoom))
#         zoom_height = max(height, int(height * zoom))

#         zoomed = background.resize(
#             (zoom_width, zoom_height),
#             Image.Resampling.LANCZOS,
#         )

#         crop_left = (zoomed.width - width) // 2
#         crop_top = (zoomed.height - height) // 2

#         background = zoomed.crop(
#             (
#                 crop_left,
#                 crop_top,
#                 crop_left + width,
#                 crop_top + height,
#             )
#         )

#     # Blur and slightly darken the background.
#     background = background.filter(ImageFilter.GaussianBlur(radius=22))
#     background = background.convert("RGBA")

#     shade = Image.new("RGBA", (width, height), (0, 0, 0, 45))
#     background = Image.alpha_composite(background, shade)

#     # Fit the original image inside the canvas without cropping.
#     # The small margin lets the blurred background remain visible.
#     available_width = int(width * 0.94)
#     available_height = int(height * 0.70)

#     image_scale = min(
#         available_width / base.width,
#         available_height / base.height,
#     )

#     image_width = max(1, int(base.width * image_scale))
#     image_height = max(1, int(base.height * image_scale))

#     foreground = base.resize(
#         (image_width, image_height),
#         Image.Resampling.LANCZOS,
#     ).convert("RGBA")

#     image_x = (width - image_width) // 2
#     image_y = max(15, (height - image_height) // 2 - int(height * 0.04))

#     background.alpha_composite(foreground, (image_x, image_y))

#     # Add a caption panel near the bottom of the frame.
#     overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
#     overlay_draw = ImageDraw.Draw(overlay)

#     panel_top = int(height * 0.74)
#     panel_bottom = int(height * 0.93)

#     overlay_draw.rounded_rectangle(
#         (24, panel_top, width - 24, panel_bottom),
#         radius=24,
#         fill=(0, 0, 0, 175),
#     )

#     frame = Image.alpha_composite(background, overlay)
#     draw = ImageDraw.Draw(frame)

#     font = get_font(max(22, int(min(width, height) * 0.045)))
#     lines = wrap_text(draw, caption, font, width - 100)

#     line_height = int(font.size * 1.3)
#     total_height = len(lines) * line_height
#     y = (panel_top + panel_bottom - total_height) // 2

#     for line in lines:
#         bbox = draw.textbbox(
#             (0, 0),
#             line,
#             font=font,
#             stroke_width=1,
#         )

#         x = (width - (bbox[2] - bbox[0])) // 2

#         draw.text(
#             (x, y),
#             line,
#             font=font,
#             fill="white",
#             stroke_width=1,
#             stroke_fill="black",
#         )

#         y += line_height

#     rgb = np.array(frame.convert("RGB"))
#     return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


# def _convert_audio(ffmpeg, source, target):
#     result = subprocess.run(
#         [
#             ffmpeg,
#             "-y",
#             "-i", source,
#             "-vn",
#             "-ac", "2",
#             "-ar", "44100",
#             "-c:a", "pcm_s16le",
#             target,
#         ],
#         capture_output=True,
#         text=True,
#     )

#     if result.returncode != 0:
#         raise RuntimeError(
#             "Could not convert narration audio: "
#             + result.stderr[-900:]
#         )


# def _run_ffmpeg(command, description):
#     result = subprocess.run(
#         command,
#         capture_output=True,
#         text=True,
#     )

#     if result.returncode != 0:
#         raise RuntimeError(
#             f"{description}: " + result.stderr[-1400:]
#         )


# def _get_scene_transitions(
#     scenes,
#     transition_mode,
#     transition_type,
# ):
#     """
#     Return one transition for every boundary between scenes.
#     The final scene has no transition after it.
#     """

#     boundary_count = max(0, len(scenes) - 1)

#     if boundary_count == 0:
#         return []

#     if transition_mode == "Same transition for all":
#         return [transition_type] * boundary_count

#     if transition_mode == "Random transitions":
#         choices = [
#             name for name in TRANSITION_NAMES
#             if name != "Cut"
#         ]
#         return [
#             random.choice(choices)
#             for _ in range(boundary_count)
#         ]

#     # Per-scene mode: each scene chooses the transition to the next.
#     return [
#         scenes[index].get("transition_to_next", "Fade")
#         for index in range(boundary_count)
#     ]


# def _build_final_video(
#     ffmpeg,
#     scene_videos,
#     scene_durations,
#     transition_names,
#     transition_duration,
#     output_path,
# ):
#     """
#     Join all scene videos using FFmpeg xfade transitions.
#     Audio uses matching short crossfades so it remains synchronized.
#     """

#     count = len(scene_videos)

#     if count == 1:
#         shutil.copy2(scene_videos[0], output_path)
#         return output_path

#     # A cut is represented by a practically instantaneous transition.
#     overlaps = []

#     for name in transition_names:
#         if name == "Cut":
#             overlaps.append(0.001)
#         else:
#             overlaps.append(transition_duration)

#     # Never let a transition consume an entire scene.
#     for index in range(len(overlaps)):
#         maximum = min(
#             scene_durations[index],
#             scene_durations[index + 1],
#         ) - 0.05

#         overlaps[index] = max(
#             0.001,
#             min(overlaps[index], maximum),
#         )

#     command = [ffmpeg, "-y"]

#     for path in scene_videos:
#         command.extend(["-i", path])

#     filters = []

#     for index in range(count):
#         filters.append(
#             f"[{index}:v]"
#             f"settb=AVTB,"
#             f"setpts=PTS-STARTPTS,"
#             f"fps={FPS},"
#             f"format=yuv420p"
#             f"[v{index}]"
#         )

#         filters.append(
#             f"[{index}:a]"
#             f"asetpts=PTS-STARTPTS"
#             f"[a{index}]"
#         )

#     current_video = "v0"
#     accumulated_duration = scene_durations[0]
#     total_overlap = 0.0

#     for index in range(1, count):
#         overlap = overlaps[index - 1]
#         total_overlap += overlap

#         offset = accumulated_duration - overlap

#         transition_name = transition_names[index - 1]
#         ffmpeg_transition = TRANSITIONS.get(
#             transition_name,
#             "fade",
#         )

#         # Keep a Cut nearly instantaneous.
#         if transition_name == "Cut":
#             ffmpeg_transition = "fade"

#         next_video = f"vx{index}"

#         filters.append(
#             f"[{current_video}][v{index}]"
#             f"xfade="
#             f"transition={ffmpeg_transition}:"
#             f"duration={overlap:.3f}:"
#             f"offset={max(0.0, offset):.3f}"
#             f"[{next_video}]"
#         )

#         current_video = next_video
#         accumulated_duration += scene_durations[index] - overlap

#     # Join narration in the same order and overlap it by the same durations.
#     current_audio = "a0"

#     for index in range(1, count):
#         next_audio = f"ax{index}"
#         overlap = overlaps[index - 1]

#         filters.append(
#             f"[{current_audio}][a{index}]"
#             f"acrossfade="
#             f"d={overlap:.3f}:"
#             f"c1=tri:c2=tri"
#             f"[{next_audio}]"
#         )

#         current_audio = next_audio

#     filters.append(f"[{current_video}]format=yuv420p[vout]")
#     filters.append(f"[{current_audio}]anull[aout]")

#     command.extend(
#         [
#             "-filter_complex",
#             ";".join(filters),
#             "-map", "[vout]",
#             "-map", "[aout]",
#             "-c:v", "libx264",
#             "-preset", "ultrafast",
#             "-crf", "23",
#             "-pix_fmt", "yuv420p",
#             "-c:a", "aac",
#             "-b:a", "160k",
#             "-movflags", "+faststart",
#             output_path,
#         ]
#     )

#     _run_ffmpeg(command, "FFmpeg could not finish the final video")
#     return output_path


# def create_video(
#     scenes,
#     output_dir,
#     video_format="Vertical 9:16 (TikTok/Reels)",
#     zoom_effect=True,
#     transition_mode="Per-scene",
#     transition_type="Fade",
#     transition_duration=0.7,
# ):
#     ffmpeg = find_ffmpeg()

#     os.makedirs(output_dir, exist_ok=True)

#     job_id = uuid.uuid4().hex[:8]
#     work_dir = os.path.join(output_dir, f"work_{job_id}")
#     os.makedirs(work_dir, exist_ok=True)

#     width, height = (
#         (1280, 720)
#         if video_format.startswith("Landscape")
#         else (720, 1280)
#     )

#     scene_videos = []
#     scene_durations = []

#     try:
#         for index, scene in enumerate(scenes, start=1):
#             audio_input = scene.get("uploaded_voice")

#             if not audio_input:
#                 raise RuntimeError(
#                     f"Scene {index}: upload a narration audio file."
#                 )

#             audio_wav = os.path.join(
#                 work_dir,
#                 f"voice_{index}.wav",
#             )

#             _convert_audio(ffmpeg, audio_input, audio_wav)

#             speech_duration = audio_duration(audio_wav, ffmpeg)

#             if speech_duration <= 0:
#                 raise RuntimeError(
#                     f"Scene {index}: narration audio is empty."
#                 )

#             duration = max(
#                 speech_duration + 0.35,
#                 float(scene.get("duration") or 0),
#             )

#             total_frames = max(1, int(round(duration * FPS)))

#             try:
#                 with Image.open(scene["image_path"]) as opened:
#                     base = opened.convert("RGB")
#             except Exception as exc:
#                 raise RuntimeError(
#                     f"Scene {index}: could not open the selected image."
#                 ) from exc

#             script = scene.get("script", "")
#             captions = split_script(script)
#             word_count = max(
#                 1,
#                 len(re.findall(r"\S+", script)),
#             )

#             timed_captions = []
#             cursor = 0.0

#             for caption in captions:
#                 caption_duration = (
#                     duration
#                     * len(caption.split())
#                     / word_count
#                 )

#                 end = cursor + caption_duration
#                 timed_captions.append((cursor, end, caption))
#                 cursor = end

#             if timed_captions:
#                 timed_captions[-1] = (
#                     timed_captions[-1][0],
#                     duration,
#                     timed_captions[-1][2],
#                 )

#             def caption_at(time_position):
#                 for start, end, caption in timed_captions:
#                     if start <= time_position < end:
#                         return caption

#                 return timed_captions[-1][2] if timed_captions else ""

#             silent_video = os.path.join(
#                 work_dir,
#                 f"scene_{index}.silent.mp4",
#             )

#             writer = cv2.VideoWriter(
#                 silent_video,
#                 cv2.VideoWriter_fourcc(*"mp4v"),
#                 FPS,
#                 (width, height),
#             )

#             if not writer.isOpened():
#                 raise RuntimeError(
#                     "OpenCV could not create a scene video. "
#                     "Check disk space and codec support."
#                 )

#             try:
#                 for frame_index in range(total_frames):
#                     time_position = frame_index / FPS

#                     frame = make_caption_frame(
#                         base=base,
#                         caption=caption_at(time_position),
#                         progress=time_position / duration,
#                         zoom_effect=zoom_effect,
#                         width=width,
#                         height=height,
#                     )

#                     writer.write(frame)
#             finally:
#                 writer.release()

#             scene_video = os.path.join(
#                 work_dir,
#                 f"scene_{index}.mp4",
#             )

#             _run_ffmpeg(
#                 [
#                     ffmpeg,
#                     "-y",
#                     "-i", silent_video,
#                     "-i", audio_wav,
#                     "-map", "0:v:0",
#                     "-map", "1:a:0",
#                     "-c:v", "libx264",
#                     "-preset", "ultrafast",
#                     "-crf", "23",
#                     "-pix_fmt", "yuv420p",
#                     "-r", str(FPS),
#                     "-c:a", "aac",
#                     "-b:a", "160k",
#                     "-af", "apad",
#                     "-t", str(duration),
#                     "-movflags", "+faststart",
#                     scene_video,
#                 ],
#                 f"FFmpeg failed while combining scene {index}",
#             )

#             scene_videos.append(scene_video)
#             scene_durations.append(duration)

#         transition_names = _get_scene_transitions(
#             scenes,
#             transition_mode,
#             transition_type,
#         )

#         transition_duration = max(
#             0.1,
#             min(float(transition_duration or 0.7), 2.0),
#         )

#         output_path = os.path.join(
#             output_dir,
#             f"video_{job_id}.mp4",
#         )

#         return _build_final_video(
#             ffmpeg=ffmpeg,
#             scene_videos=scene_videos,
#             scene_durations=scene_durations,
#             transition_names=transition_names,
#             transition_duration=transition_duration,
#             output_path=output_path,
#         )

#     finally:
#         shutil.rmtree(work_dir, ignore_errors=True)


# # import os
# # import re
# # import shutil
# # import subprocess
# # import uuid
# # import wave
# # import cv2
# # import numpy as np
# # from PIL import Image, ImageDraw, ImageFont

# # FPS = 20


# # def find_ffmpeg():
# #     path = shutil.which("ffmpeg")
# #     if not path:
# #         raise RuntimeError("FFmpeg was not found. Install FFmpeg, add its bin folder to PATH, and restart Command Prompt.")
# #     return path


# # def get_font(size):
# #     for candidate in [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf"]:
# #         if os.path.exists(candidate):
# #             return ImageFont.truetype(candidate, size=size)
# #     return ImageFont.load_default()


# # def audio_duration(path, ffmpeg):
# #     # ffprobe is installed alongside most FFmpeg distributions; WAV fallback is supported too.
# #     ffprobe = shutil.which("ffprobe")
# #     if ffprobe:
# #         result = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path], capture_output=True, text=True)
# #         if result.returncode == 0:
# #             try:
# #                 return float(result.stdout.strip())
# #             except ValueError:
# #                 pass
# #     try:
# #         with wave.open(path, "rb") as wav:
# #             return wav.getnframes() / float(wav.getframerate())
# #     except Exception:
# #         raise RuntimeError("Could not read audio duration. Please ensure FFmpeg/ffprobe is installed.")


# # def split_script(script, max_words=7):
# #     words = re.findall(r"\S+", script)
# #     return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)] or [""]


# # def wrap_text(draw, text, font, max_width):
# #     words = text.split()
# #     lines, current = [], ""
# #     for word in words:
# #         test = word if not current else current + " " + word
# #         if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
# #             current = test
# #         else:
# #             if current:
# #                 lines.append(current)
# #             current = word
# #     if current:
# #         lines.append(current)
# #     return lines


# # def make_caption_frame(base, caption, progress, zoom_effect, width, height):
# #     target_ratio = width / height
# #     iw, ih = base.size
# #     image_ratio = iw / ih
# #     if image_ratio > target_ratio:
# #         new_h, new_w = height, int(iw * height / ih)
# #     else:
# #         new_w, new_h = width, int(ih * width / iw)
# #     resized = base.resize((new_w, new_h), Image.Resampling.LANCZOS)
# #     if zoom_effect:
# #         zoom = 1.0 + 0.07 * max(0.0, min(1.0, progress))
# #         crop_w, crop_h = max(1, int(width / zoom)), max(1, int(height / zoom))
# #         crop_w, crop_h = min(crop_w, resized.width), min(crop_h, resized.height)
# #         left, top = max(0, (resized.width - crop_w) // 2), max(0, (resized.height - crop_h) // 2)
# #         resized = resized.crop((left, top, left + crop_w, top + crop_h))
# #     frame = resized.resize((width, height), Image.Resampling.LANCZOS).convert("RGB")
# #     overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
# #     od = ImageDraw.Draw(overlay)
# #     panel_top, panel_bottom = int(height * 0.70), int(height * 0.91)
# #     od.rounded_rectangle((28, panel_top, width - 28, panel_bottom), radius=24, fill=(0, 0, 0, 165))
# #     frame = Image.alpha_composite(frame.convert("RGBA"), overlay)
# #     draw = ImageDraw.Draw(frame)
# #     font = get_font(max(22, int(min(width, height) * 0.05)))
# #     lines = wrap_text(draw, caption, font, width - 100)
# #     line_height = int(font.size * 1.3)
# #     total_h = len(lines) * line_height
# #     y = (panel_top + panel_bottom - total_h) // 2
# #     for line in lines:
# #         bbox = draw.textbbox((0, 0), line, font=font, stroke_width=1)
# #         x = (width - (bbox[2] - bbox[0])) // 2
# #         draw.text((x, y), line, font=font, fill="white", stroke_width=1, stroke_fill="black")
# #         y += line_height
# #     return cv2.cvtColor(np.array(frame.convert("RGB")), cv2.COLOR_RGB2BGR)


# # def _convert_audio(ffmpeg, source, target):
# #     result = subprocess.run([ffmpeg, "-y", "-i", source, "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", target], capture_output=True, text=True)
# #     if result.returncode != 0:
# #         raise RuntimeError("Could not convert narration audio: " + result.stderr[-700:])


# # def create_video(scenes, output_dir,
# #                  video_format="Vertical 9:16 (TikTok/Reels)", zoom_effect=True):
# #     ffmpeg = find_ffmpeg()
# #     os.makedirs(output_dir, exist_ok=True)
# #     job_id = uuid.uuid4().hex[:8]
# #     work_dir = os.path.join(output_dir, f"work_{job_id}")
# #     os.makedirs(work_dir, exist_ok=True)
# #     width, height = (1280, 720) if video_format.startswith("Landscape") else (720, 1280)
# #     scene_videos, scene_audios = [], []
# #     try:
# #         for index, scene in enumerate(scenes, start=1):
# #             audio_wav = os.path.join(work_dir, f"voice_{index}.wav")
# #             audio_input = scene.get("uploaded_voice")
# #             if not audio_input:
# #                 raise RuntimeError(f"Scene {index}: upload a narration audio file.")
# #             _convert_audio(ffmpeg, audio_input, audio_wav)

# #             speech_duration = audio_duration(audio_wav, ffmpeg)
# #             if speech_duration <= 0:
# #                 raise RuntimeError(f"Scene {index}: narration audio is empty.")
# #             duration = max(speech_duration + 0.35, float(scene.get("duration") or 0))
# #             total_frames = max(1, int(duration * FPS))
# #             base = Image.open(scene["image_path"]).convert("RGB")
# #             captions = split_script(scene["script"], max_words=7)
# #             words = max(1, len(re.findall(r"\S+", scene["script"])))
# #             timed = []
# #             cursor = 0.0
# #             for caption in captions:
# #                 end = cursor + duration * (len(caption.split()) / words)
# #                 timed.append((cursor, end, caption))
# #                 cursor = end
# #             if timed:
# #                 timed[-1] = (timed[-1][0], duration, timed[-1][2])

# #             def caption_at(t):
# #                 for start, end, caption in timed:
# #                     if start <= t < end:
# #                         return caption
# #                 return timed[-1][2] if timed else ""

# #             silent_video = os.path.join(work_dir, f"scene_{index}.silent.mp4")
# #             writer = cv2.VideoWriter(silent_video, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (width, height))
# #             if not writer.isOpened():
# #                 raise RuntimeError("OpenCV could not create a scene video. Check disk space and codec support.")
# #             try:
# #                 for frame_index in range(total_frames):
# #                     t = frame_index / FPS
# #                     writer.write(make_caption_frame(base, caption_at(t), t / duration, zoom_effect, width, height))
# #             finally:
# #                 writer.release()

# #             scene_video = os.path.join(work_dir, f"scene_{index}.mp4")
# #             result = subprocess.run([
# #                 ffmpeg, "-y", "-i", silent_video, "-i", audio_wav,
# #                 "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "ultrafast",
# #                 "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
# #                 "-af", "apad", "-t", str(duration), "-movflags", "+faststart", scene_video
# #             ], capture_output=True, text=True)
# #             if result.returncode != 0:
# #                 raise RuntimeError("FFmpeg failed while combining a scene: " + result.stderr[-900:])
# #             scene_videos.append(scene_video)

# #         concat_file = os.path.join(work_dir, "concat.txt")
# #         with open(concat_file, "w", encoding="utf-8") as f:
# #             for path in scene_videos:
# #                 f.write("file '" + path.replace("\\", "/").replace("'", "'\\''") + "'\n")
# #         output_path = os.path.join(output_dir, f"video_{job_id}.mp4")
# #         result = subprocess.run([
# #             ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
# #             "-c", "copy", "-movflags", "+faststart", output_path
# #         ], capture_output=True, text=True)
# #         if result.returncode != 0:
# #             # Re-encode if stream-copy concatenation is not accepted by this FFmpeg build.
# #             result = subprocess.run([
# #                 ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
# #                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p",
# #                 "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", output_path
# #             ], capture_output=True, text=True)
# #         if result.returncode != 0:
# #             raise RuntimeError("FFmpeg could not finish the final MP4: " + result.stderr[-1200:])
# #         return output_path
# #     finally:
# #         shutil.rmtree(work_dir, ignore_errors=True)
