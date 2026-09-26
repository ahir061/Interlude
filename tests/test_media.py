import subprocess
from interlude.config import Settings
from interlude.domain import Brand
from interlude.services.media import MediaProbeService, SceneDetectionService, extract_audio
from interlude.services.speech import VadService
from interlude.services.creatives import CreativeService


def test_generated_fallback_creative_exists(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    brands = CreativeService(settings).ensure([Brand(brand_id="ninth", display_name="Ninth", category="cooking")])
    creative = brands[0].creatives[0]
    assert creative.generated
    assert getattr(creative, "width", None) == 640 and getattr(creative, "height", None) == 360
    assert 5 <= creative.duration_sec <= 10
    assert MediaProbeService(settings).probe(creative.local_path, "ad").codec == "h264"


def test_real_mp4_scene_detection_and_cpu_vad(tmp_path):
    path = tmp_path / "cuts.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:s=320x180:r=25:d=3",
                    "-f", "lavfi", "-i", "color=blue:s=320x180:r=25:d=3", "-f", "lavfi", "-i",
                    "anullsrc=r=16000:cl=mono", "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                    "-map", "[v]", "-map", "2:a", "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(path)], check=True, capture_output=True)
    settings = Settings(_env_file=None)
    scenes = SceneDetectionService(settings).detect(path)
    assert len(scenes) == 2
    assert abs(scenes[1].start_sec - 3) < 0.1
    audio = tmp_path / "speech.wav"
    extract_audio(settings, path, audio)
    assert VadService().detect(audio) == []
