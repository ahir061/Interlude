"""Bounded speech analysis with conservative overlap at episode chunk seams."""
import json
from pathlib import Path
from uuid import uuid4

from interlude.domain import Interval, Transcript, TranscriptSegment, Word
from interlude.providers.base import ProviderError
from interlude.providers.perception import digest
from interlude.services.media import run_media


def chunk_windows(duration: float, chunk_sec: float, overlap_sec: float):
    core = 0.0
    while core < duration:
        start = max(0, core-overlap_sec)
        end = min(duration, core+chunk_sec+overlap_sec)
        yield start, end-start
        core += chunk_sec


def merge_chunk_transcripts(chunks: list[tuple[float, Transcript]], duration: float) -> Transcript:
    segments, seen_words, seen_segments = [], set(), set()
    for offset, transcript in chunks:
        for segment in transcript.segments:
            if offset+segment.end_sec > duration+0.5:
                raise ProviderError("asr_timestamp_outside_video")
            start, end = offset+segment.start_sec, min(duration, offset+segment.end_sec)
            if end <= start:
                continue
            words = []
            for word in segment.words:
                if offset+word.end_sec > duration+0.5:
                    raise ProviderError("asr_timestamp_outside_video")
                ws, we = offset+word.start_sec, min(duration, offset+word.end_sec)
                key = (round(ws, 3), round(we, 3), word.text.strip())
                if key not in seen_words and we > ws:
                    seen_words.add(key)
                    words.append(Word(start_sec=ws, end_sec=we, text=word.text))
            key = (round(start, 3), round(end, 3), segment.text.strip())
            if key not in seen_segments:
                seen_segments.add(key)
                segments.append(TranscriptSegment(start_sec=start, end_sec=end, text=segment.text, words=words))
            elif words:
                next(s for s in segments if (round(s.start_sec,3),round(s.end_sec,3),s.text.strip()) == key).words.extend(words)
    return Transcript(segments=sorted(segments, key=lambda s: (s.start_sec,s.end_sec)))


def merge_intervals(chunks: list[tuple[float, list[Interval]]], duration: float) -> list[Interval]:
    intervals = sorted((offset+i.start_sec, min(duration, offset+i.end_sec))
                       for offset, items in chunks for i in items)
    merged = []
    for start, end in intervals:
        if end <= start:
            continue
        if merged and start <= merged[-1].end_sec:
            merged[-1].end_sec = max(merged[-1].end_sec, end)
        else:
            merged.append(Interval(start_sec=start, end_sec=end))
    return merged


class EpisodeAudioService:
    def __init__(self, settings, asr, vad):
        self.settings, self.asr, self.vad = settings, asr, vad

    def analyze(self, source: Path, duration: float, work: Path, video_hash: str, progress=lambda done,total: None):
        s = self.settings
        windows = list(chunk_windows(duration,s.audio_chunk_sec,s.audio_chunk_overlap_sec))
        transcripts, voices, cache_hits = [], [], 0
        for index,(offset,length) in enumerate(windows):
            progress(index,len(windows))
            key = digest({"version": "episode-audio-1", "video":video_hash,"offset":offset,"length":length,
                          "asr":s.asr_model,"language":s.asr_language,"words":s.asr_word_timestamps,
                          "vad":"silero-6-pad150-threshold0.4"})
            target = s.data_dir/"audio_cache"/f"{key}.json"
            transcript = voice = None
            if s.semantic_cache_enabled and target.exists():
                try:
                    data=json.loads(target.read_text())
                    transcript=Transcript.model_validate(data["transcript"])
                    voice=[Interval.model_validate(v) for v in data["vad"]]
                    if any(i.end_sec > length+0.5 for i in [*transcript.segments,*transcript.speech_words,*voice]):
                        raise ValueError("cached_timestamp_outside_chunk")
                    cache_hits+=1
                except (ValueError,KeyError,TypeError,OSError):
                    transcript=voice=None
            if transcript is None:
                audio=work/f"speech-{index:05d}.wav"
                try:
                    run_media([s.ffmpeg_bin,"-v","error","-y","-ss",str(offset),"-i",str(source),
                        "-t",str(length),"-vn","-ac","1","-ar","16000","-c:a","pcm_s16le",str(audio)],
                        timeout=s.media_command_timeout_sec)
                    transcript=self.asr.transcribe(audio)
                    voice=self.vad.detect(audio)
                    if any(i.end_sec > length+0.5 for i in [*transcript.segments,*transcript.speech_words,*voice]):
                        raise ProviderError("speech_timestamp_outside_chunk")
                    target.parent.mkdir(parents=True,exist_ok=True)
                    temporary=target.with_suffix(f".{uuid4().hex}.tmp")
                    try:
                        temporary.write_text(json.dumps({"transcript":transcript.model_dump(),
                                                         "vad":[i.model_dump() for i in voice]}))
                        temporary.replace(target)
                    finally:
                        temporary.unlink(missing_ok=True)
                finally:
                    audio.unlink(missing_ok=True)
            transcripts.append((offset,transcript))
            voices.append((offset,voice))
            progress(index+1,len(windows))
        return merge_chunk_transcripts(transcripts,duration), merge_intervals(voices,duration), {
            "chunks":len(windows),"cache_hits":cache_hits,"chunk_sec":s.audio_chunk_sec,
            "overlap_sec":s.audio_chunk_overlap_sec}
