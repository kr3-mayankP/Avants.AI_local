"""AI service functions split out of ai_services.py."""

from _ai_service_common import *

# Moved from ai_services.py: AudioTooLargeError
class AudioTooLargeError(Exception):
    """Raised when a recorded answer is too long/large for Whisper's 25MB
    cap (likely hit with the camera on, since video is far larger per
    second than audio-only) - callers should show a specific, actionable
    message instead of the generic transcription-failed one."""
    pass

# Moved from ai_services.py: extract_audio_for_transcription
def extract_audio_for_transcription(input_path):
    """Strips an uploaded video down to just its audio track, compressed to
    a small mono MP3, before handing it to Whisper - a video file's picture
    data is what actually eats into the 25MB cap, not the speech, so this
    lets much longer uploads fit under that same fixed limit. Falls back to
    returning the original path untouched (not raising) if ffmpeg isn't on
    PATH or the conversion fails for any reason - callers always get back a
    valid, existing file path, just not necessarily a smaller one."""
    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return input_path

    out_path = f"{input_path}.audio.mp3"
    try:
        result = subprocess.run(
            [ffmpeg, "-y", "-i", input_path, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", out_path],
            capture_output=True, timeout=120,
        )
        if result.returncode == 0 and os.path.getsize(out_path) > 0:
            return out_path
    except Exception:
        logger.exception("ffmpeg audio extraction failed - falling back to the original upload")

    if os.path.exists(out_path):
        try:
            os.unlink(out_path)
        except OSError:
            pass
    return input_path

# Moved from ai_services.py: transcribe_audio
#------------------------------------------------------------------------
# def transcribe_audio(file_path):
#     """Speech-to-text for a candidate's recorded interview answer."""
#     with open(file_path, "rb") as f:
#------------------------------------------------------------------------
def transcribe_audio(file_path):
    """Speech-to-text for a candidate's recorded interview answer."""
    if client is None:
        raise RuntimeError(
            "Audio transcription requires OPENAI_API_KEY; it is not configured."
        )

    with open(file_path, "rb") as f:
        try:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=f)
        except openai.BadRequestError as e:
            if "size" in str(e).lower() or "25 mb" in str(e).lower() or "maximum content" in str(e).lower():
                raise AudioTooLargeError(
                    "That answer was too long to transcribe - recordings are capped at 25MB, which "
                    "video answers can hit in roughly a minute or two depending on quality. Try a "
                    "shorter answer, or turn off your camera for longer responses."
                ) from e
            raise
    return transcript.text.strip()

# Moved from ai_services.py: audio_file_extension
def audio_file_extension(uploaded_filename):
    """Picks the suffix for the temp file a recorded answer gets written to
    before transcription, from whatever filename the browser's upload sent.
    Matters because Whisper's API decides how to decode the file from this
    suffix - Safari (desktop and iOS) doesn't support WebM at all and records
    mp4 instead, so hardcoding ".webm" regardless of what was actually
    uploaded silently breaks transcription on any non-WebM browser."""
    import os as _os
    ext = _os.path.splitext(uploaded_filename or "")[1].lower()
    return ext if ext in _ALLOWED_AUDIO_EXTENSIONS else ".webm"

# Moved from ai_services.py: synthesize_speech
def synthesize_speech(text, out_path):
    """Text-to-speech for an AI interview question — mirrors app.py's /speak route."""
    from google.cloud import texttospeech

    tts_client = texttospeech.TextToSpeechClient()
    input_text = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Wavenet-D",
        ssml_gender=texttospeech.SsmlVoiceGender.MALE,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0,
    )
    response = tts_client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)
    with open(out_path, "wb") as out:
        out.write(response.audio_content)

