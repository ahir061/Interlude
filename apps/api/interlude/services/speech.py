from pathlib import Path
from interlude.domain import Interval


class VadService:
    """Packaged Silero weights are cached in the installed wheel, run on CPU."""
    def detect(self, audio: Path) -> list[Interval]:
        import soundfile as sf
        import torch
        from silero_vad import load_silero_vad, get_speech_timestamps
        torch.set_num_threads(1)
        samples, rate = sf.read(str(audio), dtype="float32")
        if rate != 16000 or samples.ndim != 1:
            raise ValueError("VAD requires mono 16kHz audio")
        model = load_silero_vad().to("cpu")
        timestamps = get_speech_timestamps(torch.from_numpy(samples), model, sampling_rate=rate,
                                          return_seconds=True, speech_pad_ms=150, threshold=0.4)
        return [Interval(start_sec=t["start"], end_sec=t["end"]) for t in timestamps]
