
from pathlib import Path
from functools import lru_cache
import shutil

import torch
import torchaudio
from chatterbox.tts_turbo import ChatterboxTurboTTS


BASE_DIR = Path(__file__).resolve().parent
VOICE_DIR = BASE_DIR / "voice_reference"
AUDIO_DIR = BASE_DIR / "generated_voice"

VOICE_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

SAVED_REFERENCE = VOICE_DIR / "reference_voice.wav"


def save_reference(uploaded_path: str | None) -> str:
    """Save an uploaded voice reference for reuse in future videos."""
    if uploaded_path:
        source = Path(uploaded_path)

        if not source.is_file():
            raise FileNotFoundError("The uploaded reference audio was not found.")

        destination = VOICE_DIR / f"reference{source.suffix.lower()}"
        shutil.copy2(source, destination)

        # Return the saved path. Chatterbox can load common audio formats.
        return str(destination)

    # If no new upload is provided, reuse the previously saved reference.
    if SAVED_REFERENCE.exists():
        return str(SAVED_REFERENCE)

    # Reuse a previously saved reference in another supported format.
    for extension in (".wav", ".mp3", ".flac", ".ogg", ".m4a"):
        candidate = VOICE_DIR / f"reference{extension}"
        if candidate.exists():
            return str(candidate)

    raise ValueError(
        "Upload your reference voice recording first. "
        "It will be saved for later videos."
    )



@lru_cache(maxsize=1)
def get_voice_model():
    """
    Load Chatterbox Turbo once and reuse it.
    Run on CPU to avoid requiring a compatible GPU.
    """
    return ChatterboxTurboTTS.from_pretrained(
        device="cpu"
    )


def generate_speech(
    narration_text: str,
    reference_audio: str,
    output_path: str,
) -> str:
    """Generate NEW spoken words using the reference voice."""
    text = (narration_text or "").strip()

    if not text:
        raise ValueError("This scene has no narration text.")

    reference = Path(reference_audio)
    if not reference.is_file():
        raise FileNotFoundError(f"Reference audio not found: {reference}")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    model = get_voice_model()

    # The reference audio controls the voice identity.
    # The narration text controls which words are spoken.
    with torch.inference_mode():
        waveform = model.generate(
            text,
            audio_prompt_path=str(reference),
        )

    if waveform.ndim == 1:
        waveform = waveform.unsqueeze(0)

    waveform = waveform.detach().cpu().float()

    torchaudio.save(
        str(output),
        waveform,
        model.sr,
    )

    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError("The voice model did not create an audio file.")

    return str(output.resolve())
