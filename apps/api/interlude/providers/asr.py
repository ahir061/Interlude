import time
from pathlib import Path
from typing import Protocol

import httpx
from interlude.config import Settings
from interlude.domain import Transcript, TranscriptSegment, Word
from interlude.providers.base import retry


class AsrProvider(Protocol):
    def transcribe(self, audio: Path) -> Transcript: ...


class GroqWhisperProvider:
    def __init__(self, settings: Settings, client: httpx.Client | None = None, sleep=time.sleep):
        self.settings, self.client, self.sleep = settings, client, sleep

    def transcribe(self, audio: Path) -> Transcript:
        def request():
            granularities = ["segment", "word"] if self.settings.asr_word_timestamps else ["segment"]
            with audio.open("rb") as source:
                args = dict(headers={"Authorization": f"Bearer {self.settings.groq_api_key.get_secret_value()}"},
                    data={"model": self.settings.asr_model, "language": "bn", "response_format": "verbose_json",
                          "temperature": "0", "timestamp_granularities[]": granularities},
                    files={"file": ("speech.wav", source, "audio/wav")},
                    timeout=self.settings.asr_request_timeout_sec)
                if self.client:
                    response = self.client.post("https://api.groq.com/openai/v1/audio/transcriptions", **args)
                else:
                    with httpx.Client() as client:
                        response = client.post("https://api.groq.com/openai/v1/audio/transcriptions", **args)
            response.raise_for_status()
            raw = response.json()
            segments = raw["segments"]
            if not isinstance(segments, list) or (raw.get("text", "").strip() and not segments):
                raise ValueError("missing timestamp segments")
            words = [Word(start_sec=w["start"], end_sec=w["end"], text=w["word"])
                     for w in raw.get("words", []) if w["end"] > w["start"]]
            normalized = [TranscriptSegment(start_sec=s["start"], end_sec=s["end"], text=s["text"]) for s in segments]
            if words and not normalized:
                raise ValueError("words without transcript segments")
            # Provider word and segment envelopes can disagree. Preserve every valid
            # word once, including words straddling or outside segment envelopes.
            for word in words:
                segment = min(normalized, key=lambda s: max(s.start_sec-word.end_sec, word.start_sec-s.end_sec, 0))
                segment.words.append(word)
            return Transcript(segments=normalized)
        return retry(request, "asr", self.settings.asr_max_retries, self.sleep)
