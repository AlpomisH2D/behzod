import logging
import subprocess
from pathlib import Path

import config

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".oga", ".opus"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
SUPPORTED_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS


class FfmpegError(Exception):
    pass


class UnsupportedFormatError(Exception):
    pass


def _run(command: list[str], error_prefix: str) -> subprocess.CompletedProcess:
    """Runs an ffmpeg/ffprobe subprocess with a hard timeout - without one, a
    malformed or unusually large input can hang the call (and the caller)
    forever instead of failing visibly."""
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=config.FFMPEG_SUBPROCESS_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired as exc:
        logger.exception("%s: jarayon %ss dan keyin to'xtatildi", error_prefix, config.FFMPEG_SUBPROCESS_TIMEOUT_SECONDS)
        raise FfmpegError(f"{error_prefix}: jarayon muddati tugadi") from exc
    return result


def ensure_audio(input_path: Path, output_dir: Path) -> Path:
    """Returns a path to an audio file suitable for transcription.

    Audio inputs pass through untouched; video inputs are transcoded via ffmpeg.
    """
    suffix = input_path.suffix.lower()
    if suffix in AUDIO_EXTENSIONS:
        return input_path
    if suffix not in VIDEO_EXTENSIONS:
        raise UnsupportedFormatError(f"Qo'llab-quvvatlanmaydigan fayl formati: {suffix}")
    return extract_audio(input_path, output_dir / f"{input_path.stem}.mp3")


def extract_audio(input_path: Path, output_path: Path) -> Path:
    logger.debug("Videodan audio ajratilmoqda: %s", input_path.name)
    command = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-vn",
        "-acodec", "libmp3lame",
        "-ar", "16000",
        "-ac", "1",
        str(output_path),
    ]
    result = _run(command, "ffmpeg audio ajratishda xato")
    if result.returncode != 0:
        logger.error("ffmpeg audio ajratishda xato (%s): %s", input_path.name, result.stderr.strip())
        raise FfmpegError(f"ffmpeg audio ajratishda xato: {result.stderr.strip()}")
    logger.debug("Audio ajratildi: %s", output_path.name)
    return output_path


def get_duration(path: Path) -> float | None:
    """Real audio duration in seconds via ffprobe, or None if it can't be read."""
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = _run(command, "ffprobe davomiylikni aniqlashda xato")
    except FfmpegError:
        return None
    if result.returncode != 0:
        logger.warning("ffprobe davomiylikni aniqlay olmadi (%s): %s", path.name, result.stderr.strip())
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        logger.warning("ffprobe qaytargan davomiylikni parse qilib bo'lmadi (%s): %r", path.name, result.stdout)
        return None


def split_into_chunks(input_path: Path, output_dir: Path, chunk_seconds: float) -> list[Path]:
    """Splits audio into consecutive `chunk_seconds`-long files (last one may
    be shorter). Used to reduce Whisper's word-timestamp drift on long audio.
    """
    duration = get_duration(input_path)
    if duration is None:
        raise FfmpegError("Audio davomiyligini aniqlab bo'lmadi")

    logger.debug("Audio %.1fs uzunlikda %ss bo'laklarga bo'linmoqda: %s", duration, chunk_seconds, input_path.name)
    chunk_paths: list[Path] = []
    start = 0.0
    index = 0
    while start < duration:
        chunk_path = output_dir / f"chunk_{index:03d}.mp3"
        command = [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-ss", str(start),
            "-t", str(chunk_seconds),
            "-acodec", "libmp3lame",
            "-ar", "16000",
            "-ac", "1",
            str(chunk_path),
        ]
        result = _run(command, "ffmpeg audio bo'laklashda xato")
        if result.returncode != 0:
            logger.error("ffmpeg audio bo'laklashda xato (bo'lak %d, %s): %s", index, input_path.name, result.stderr.strip())
            raise FfmpegError(f"ffmpeg audio bo'laklashda xato: {result.stderr.strip()}")
        chunk_paths.append(chunk_path)
        start += chunk_seconds
        index += 1
    logger.debug("Audio %d ta bo'lakka bo'lindi: %s", len(chunk_paths), input_path.name)
    return chunk_paths
