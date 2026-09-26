import json
import subprocess
from fractions import Fraction
from pathlib import Path

from interlude.config import Settings
from interlude.domain import Frame, Scene, VideoMetadata


class MediaError(RuntimeError):
    pass


def run_media(command: list[str], timeout: float = 180) -> str:
    try:
        return subprocess.run(command, check=True, capture_output=True, timeout=timeout, text=True).stdout
    except (subprocess.SubprocessError, OSError):
        raise MediaError("media_processing_failed") from None


class MediaProbeService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def probe(self, path: Path | str, video_id: str = "video") -> VideoMetadata:
        data = json.loads(run_media([self.settings.ffprobe_bin, "-v", "error", "-show_format", "-show_streams",
                                    "-of", "json", str(path)], timeout=30))
        stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
        if stream is None or "mp4" not in data.get("format", {}).get("format_name", ""):
            raise MediaError("invalid_mp4")
        return VideoMetadata(id=video_id, duration_sec=float(data["format"]["duration"]), width=stream["width"],
            height=stream["height"], frame_rate=float(Fraction(stream["avg_frame_rate"])), codec=stream["codec_name"],
            has_audio=any(s.get("codec_type") == "audio" for s in data["streams"]),
            source_url=f"/api/videos/{video_id}/media")


class SceneDetectionService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def detect(self, path: Path) -> list[Scene]:
        from scenedetect import open_video, SceneManager, StatsManager
        from scenedetect.detectors import ContentDetector
        video = open_video(str(path))
        stats = StatsManager()
        manager = SceneManager(stats_manager=stats)
        manager.add_detector(ContentDetector(threshold=self.settings.scene_threshold, min_scene_len=12))
        manager.detect_scenes(video=video, show_progress=False)
        detected = manager.get_scene_list(start_in_scene=True)
        scenes = []
        for i, (start, end) in enumerate(detected):
            values = stats.get_metrics(start.get_frames(), ["content_val"]) if i else [0]
            # content_val is a measured 0..255 difference. Saturate at twice threshold.
            strength = min(float(values[0] or 0) / (2 * self.settings.scene_threshold), 1)
            scenes.append(Scene(id=f"scene_{i+1:03d}", start_sec=start.get_seconds(), end_sec=end.get_seconds(),
                                boundary_score=strength))
        if not scenes:
            duration = MediaProbeService(self.settings).probe(path).duration_sec
            scenes = [Scene(id="scene_001", start_sec=0, end_sec=duration)]
        return scenes


def extract_audio(settings: Settings, source: Path, target: Path):
    run_media([settings.ffmpeg_bin, "-v", "error", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000",
               "-c:a", "pcm_s16le", str(target)])


def extract_window(settings: Settings, source: Path, timestamp: float, duration: float, directory: Path) -> list[Frame]:
    directory.mkdir(parents=True, exist_ok=True)
    start, end = max(0, timestamp - 5), min(duration - 0.05, timestamp + 5)
    frames = []
    t = start
    while t <= end:
        path = directory / f"frame_{len(frames):03d}.jpg"
        run_media([settings.ffmpeg_bin, "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(source),
                   "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "3", str(path)], timeout=30)
        if not path.is_file():
            raise MediaError("frame_extraction_failed")
        frames.append(Frame(timestamp_sec=round(t, 3), path=str(path)))
        t += 1
    return frames
