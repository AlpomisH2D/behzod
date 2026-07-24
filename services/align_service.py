import difflib
import re

from models.types import AlignedWord, Word

_TRIM_PATTERN = re.compile(r"^[^\w']+|[^\w']+$", re.UNICODE)


def _normalize(token: str) -> str:
    return _TRIM_PATTERN.sub("", token.lower())


def align_words(
    original_text: str | None,
    groq_words: list[Word],
    audio_duration: float | None = None,
) -> list[AlignedWord]:
    """Times the words of `original_text` using Groq's word-level transcript.

    Text comes from the (possibly user-corrected) script; timing comes from Groq.
    If no script is supplied, Groq's own words are returned unchanged.

    `audio_duration` (the real length of the audio, from Groq's own response) is
    the only extra anchor ever used. Script words with no matching Groq word get
    interpolated strictly between two real anchors - the previous real word's end
    and either the next real word's start or, for a trailing unmatched stretch,
    the real audio duration. When neither anchor is available, words collapse to
    the last known real timestamp instead of being spread out at an invented pace.
    """
    if not original_text or not original_text.strip():
        return [AlignedWord(text=w.text, start=w.start, end=w.end) for w in groq_words]

    display_tokens = original_text.split()
    if not groq_words:
        return _pack_without_timing(display_tokens, audio_duration)

    groq_norm = [_normalize(w.text) for w in groq_words]
    orig_norm = [_normalize(t) for t in display_tokens]

    matcher = difflib.SequenceMatcher(None, groq_norm, orig_norm, autojunk=False)
    aligned: list[AlignedWord | None] = [None] * len(display_tokens)
    last_end = groq_words[0].start

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                gw = groq_words[i1 + offset]
                aligned[j1 + offset] = AlignedWord(display_tokens[j1 + offset], gw.start, gw.end)
            if i2 > i1:
                last_end = groq_words[i2 - 1].end
        elif tag == "delete":
            if i2 > i1:
                last_end = groq_words[i2 - 1].end
        else:  # 'replace' or 'insert' - original has words with no direct Groq match
            if i2 > i1:
                bucket_start = groq_words[i1].start
                bucket_end = groq_words[i2 - 1].end
            else:
                bucket_start = last_end
                if i1 < len(groq_words):
                    bucket_end = groq_words[i1].start
                elif audio_duration is not None:
                    bucket_end = audio_duration
                else:
                    bucket_end = last_end
            for orig_idx, (start, end) in zip(
                range(j1, j2), _interpolate(bucket_start, bucket_end, j2 - j1)
            ):
                aligned[orig_idx] = AlignedWord(display_tokens[orig_idx], start, end)
            last_end = bucket_end if bucket_end > bucket_start else last_end

    return [w for w in aligned if w is not None]


def _interpolate(start: float, end: float, count: int) -> list[tuple[float, float]]:
    if count <= 0:
        return []
    if end <= start:
        # No real time budget between the two anchors (or no second anchor at
        # all) - collapse every word onto the one real timestamp we do have
        # rather than inventing a pace. A wrong-but-bounded timestamp is far
        # safer than one that silently drifts away from the real audio.
        return [(start, start) for _ in range(count)]
    step = (end - start) / count
    return [(start + i * step, start + (i + 1) * step) for i in range(count)]


def _pack_without_timing(
    display_tokens: list[str], audio_duration: float | None = None
) -> list[AlignedWord]:
    if audio_duration:
        return [
            AlignedWord(t, start, end)
            for t, (start, end) in zip(display_tokens, _interpolate(0.0, audio_duration, len(display_tokens)))
        ]
    return [AlignedWord(t, 0.0, 0.0) for t in display_tokens]
