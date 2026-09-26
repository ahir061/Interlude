from interlude.config import Settings
from interlude.domain import Interval, Transcript, TranscriptSegment, Word


def test_overlapping_chunks_preserve_absolute_speech_at_seam(tmp_path):
    from interlude.services.episode_audio import merge_chunk_transcripts, merge_intervals
    left = Transcript(segments=[TranscriptSegment(start_sec=8, end_sec=12, text="left",
        words=[Word(start_sec=9.8, end_sec=10.4, text="cross")])])
    right = Transcript(segments=[TranscriptSegment(start_sec=0, end_sec=4, text="right",
        words=[Word(start_sec=1.8, end_sec=2.4, text="cross"), Word(start_sec=3, end_sec=3.5, text="next")])])
    result = merge_chunk_transcripts([(0, left), (8, right)], 20)
    assert len(result.speech_words) == 2
    assert result.speech_words[0].start_sec == 9.8
    assert result.speech_words[-1].start_sec == 11
    merged = merge_intervals([(0, [Interval(start_sec=9.5, end_sec=12)]),
                              (8, [Interval(start_sec=1.5, end_sec=4.5)])], 20)
    assert len(merged) == 1 and merged[0].end_sec == 12.5
    from interlude.services.scene_builder import DialogueSafetyGate
    assert not DialogueSafetyGate(Settings(_env_file=None)).evaluate(10, result, merged, 20)["safe"]


def test_chunk_plan_is_bounded_overlapping_and_covers_episode():
    from interlude.services.episode_audio import chunk_windows
    windows = list(chunk_windows(3700, 300, 2))
    assert windows[0] == (0, 302)
    assert windows[-1][0] + windows[-1][1] == 3700
    assert all(length <= 304 for _, length in windows)
    assert all(a + length > b for (a, length), (b, _) in zip(windows, windows[1:]))


def test_invalid_chunk_timestamps_fail_closed():
    import pytest
    from interlude.services.episode_audio import merge_chunk_transcripts
    from interlude.providers.base import ProviderError
    with pytest.raises(ProviderError):
        merge_chunk_transcripts([(0, Transcript(segments=[TranscriptSegment(start_sec=0,end_sec=30,text="bad")]))], 10)
