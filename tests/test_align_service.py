from models.types import Word
from services.align_service import align_words


def test_align_identical_text_copies_groq_timing_exactly():
    groq_words = [
        Word("salom", 0.0, 0.4),
        Word("dunyo", 0.4, 0.9),
    ]
    result = align_words("Salom dunyo", groq_words)

    assert [w.text for w in result] == ["Salom", "dunyo"]
    assert [(w.start, w.end) for w in result] == [(0.0, 0.4), (0.4, 0.9)]


def test_align_ignores_groq_filler_word_not_in_script():
    groq_words = [
        Word("salom", 0.0, 0.4),
        Word("ээ", 0.4, 0.6),
        Word("dunyo", 0.6, 1.0),
    ]
    result = align_words("Salom dunyo", groq_words)

    assert [w.text for w in result] == ["Salom", "dunyo"]
    assert result[0].start == 0.0
    assert result[1].end == 1.0


def test_align_interpolates_script_word_missing_from_groq():
    groq_words = [
        Word("salom", 0.0, 1.0),
        Word("dunyo", 2.0, 3.0),
    ]
    result = align_words("Salom katta dunyo", groq_words)

    assert [w.text for w in result] == ["Salom", "katta", "dunyo"]
    assert result[0].start == 0.0 and result[0].end == 1.0
    assert result[2].start == 2.0 and result[2].end == 3.0
    # interpolated word sits strictly between the two anchors
    assert result[0].end <= result[1].start
    assert result[1].end <= result[2].start


def test_align_without_script_passes_groq_words_through():
    groq_words = [
        Word("salom", 0.0, 0.4),
        Word("dunyo", 0.4, 0.9),
    ]
    result = align_words(None, groq_words)

    assert [(w.text, w.start, w.end) for w in result] == [
        ("salom", 0.0, 0.4),
        ("dunyo", 0.4, 0.9),
    ]


def test_align_with_empty_groq_words_and_no_duration_collapses_to_zero():
    result = align_words("Salom dunyo", [])

    assert [w.text for w in result] == ["Salom", "dunyo"]
    assert all((w.start, w.end) == (0.0, 0.0) for w in result)


def test_align_with_empty_groq_words_and_known_duration_spreads_evenly():
    result = align_words("Salom dunyo", [], audio_duration=4.0)

    assert [w.text for w in result] == ["Salom", "dunyo"]
    assert result[0].start == 0.0
    assert result[-1].end == 4.0
    assert result[0].end <= result[1].start


# --- Regression tests for the "sentence drifts behind the audio" bug ---
#
# Root cause: when Groq's transcript ends (or badly mis-transcribes) before a
# script sentence does, the old code stacked the leftover script words at a
# hardcoded 0.3s/word pace with no ceiling. On real audio that pace rarely
# matches actual speech, so the fabricated timestamps ran further and further
# past the real audio the longer the untranscribed tail was - exactly the
# "synced at first, one sentence falls behind near the end" symptom.


def test_align_trailing_unmatched_sentence_is_bounded_by_real_audio_duration():
    # Groq only heard the first 5 seconds of a much longer (49s) recording.
    groq_words = [
        Word("Bugun", 0.0, 0.4),
        Word("ob-havo", 0.4, 0.9),
        Word("juda", 0.9, 1.2),
        Word("issiq", 1.2, 1.7),
        Word("edi", 1.7, 2.0),
    ]
    script = (
        "Bugun ob-havo juda issiq edi. "
        "Shuning uchun biz butun kun davomida uyda o'tirishga qaror qildik "
        "va salqin joyni qidirdik."
    )

    result = align_words(script, groq_words, audio_duration=49.0)

    # The untranscribed tail must never run past the real, known audio length.
    assert result[-1].end == 49.0
    # ...and it must start right where the real (Groq-anchored) speech ended,
    # not at some arbitrarily earlier or later point.
    assert result[5].text == "Shuning"
    assert result[5].start == 2.0  # first word of the missed tail
    # Every word stays inside [0, audio_duration] - no runaway drift.
    assert all(0.0 <= w.start <= 49.0 and 0.0 <= w.end <= 49.0 for w in result)


def test_align_trailing_unmatched_sentence_without_duration_does_not_drift():
    # Same as above, but the real audio duration isn't known at all (e.g. an
    # older Groq response without a `duration` field). The old code would
    # have kept fabricating timestamps 0.3s apart forever; the fix must
    # instead pin every unanchored word to the last real timestamp we have,
    # never invent a pace that has no grounding in real data.
    groq_words = [Word("Bugun", 0.0, 0.4), Word("issiq", 0.4, 2.0)]
    script = "Bugun issiq. Va bu haqida yana ko'p gapirish mumkin edi albatta."

    result = align_words(script, groq_words, audio_duration=None)

    tail = result[2:]  # words with no Groq match
    assert all(w.start == 2.0 and w.end == 2.0 for w in tail)
