# Local Multi-Scene Video Maker

A beginner-friendly Windows app for creating videos from up to 8 images/scenes using audio files uploaded from your computer. No API key or online voice service is required.

## How audio works

- **Shared narration audio:** Upload one audio file once at the top of the Storyboard tab. This audio is used for every scene by default.
- **Optional scene-specific recording:** If you recorded separate narration for a particular scene, upload it in that scene. It overrides the shared audio for that scene only.
- **Narration text / subtitles:** Type the words you want displayed as captions. The app does not convert text to speech, and captions are approximate rather than speech-recognition aligned.

**Important:** The shared audio file is the same audio track used in each scene that does not have its own recording. It does not clone a voice or create different spoken sentences for each scene. If you want different narration in every scene, upload separate recordings for those scenes, or use one complete narration file split into scene-specific clips.

## Requirements

- Windows 10/11
- Python 3.11 recommended
- FFmpeg (including `ffprobe`) installed and available on PATH

Check installation:

```bat
python --version
ffmpeg -version
ffprobe -version
```

## Install and run

Extract the project, open Command Prompt in the `local_image_video_starter` folder, then run:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:7860` if the browser does not open automatically. The app runs locally and does not create a public share link.

## Create a video

1. Upload one common narration audio file at the top of the Storyboard tab.
2. For each scene you want, upload an image and enter the matching narration text for captions.
3. Optionally upload a separate recording in a scene to override the shared audio for that scene.
4. Leave unused scenes empty.
5. Choose vertical or landscape format and whether to use gentle zoom.
6. Click **Generate narrated MP4**, then preview or download the result.

## Notes

- Each scene lasts at least as long as its selected audio plus a short padding interval. The duration field can make a scene longer; it does not cut off narration.
- Scenes are joined in storyboard order with cuts.
- Images are still frames with optional zoom; the app does not generate new AI motion.
