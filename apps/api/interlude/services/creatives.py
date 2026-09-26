import hashlib
import shutil
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from interlude.config import ROOT, Settings
from interlude.domain import Brand, Creative
from interlude.services.media import MediaProbeService, run_media


class CreativeService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def ensure(self, brands: list[Brand]) -> list[Brand]:
        for brand in brands:
            directory = self.settings.data_dir / "ads" / brand.brand_id
            directory.mkdir(parents=True, exist_ok=True)
            if not brand.creatives:
                brand.creatives = [Creative(creative_id=f"{brand.brand_id}_fallback", duration_sec=6)]
            for creative in brand.creatives:
                target = directory / f"{creative.creative_id}.mp4"
                original = (ROOT / creative.url).resolve()
                allowed = original.is_relative_to((self.settings.data_dir / "ads").resolve())
                allowed = allowed or original.is_relative_to((ROOT / "ads").resolve())
                if not target.exists() and allowed and original.is_file():
                    shutil.copyfile(original, target)
                marker = target.with_suffix(".generated")
                if not target.exists():
                    self._generate(brand, target)
                    marker.write_text("synthetic development creative, 6 seconds\n")
                metadata = MediaProbeService(self.settings).probe(target, creative.creative_id)
                creative.duration_sec = metadata.duration_sec
                creative.width, creative.height = metadata.width, metadata.height
                creative.local_path = str(target.resolve())
                creative.url = f"/api/ads/{brand.brand_id}/{creative.creative_id}"
                creative.generated = marker.exists()
        return brands

    def _generate(self, brand: Brand, target: Path):
        digest = hashlib.sha256(brand.brand_id.encode()).digest()
        background = tuple(30 + c % 45 for c in digest[:3])
        frame = Image.new("RGB", (640, 360), background)
        draw = ImageDraw.Draw(frame)
        font = ImageFont.load_default(size=32)
        for y, text in ((75, brand.display_name), (150, "\n".join(textwrap.wrap(brand.category, 28))),
                        (285, "Synthetic demo advertisement")):
            draw.multiline_text((32, y), text, fill="white", font=font)
        image = target.with_suffix(".png")
        temporary = target.with_name(target.stem + ".tmp.mp4")
        try:
            frame.save(image)
            run_media([self.settings.ffmpeg_bin, "-v", "error", "-y", "-loop", "1", "-i", str(image),
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "6", "-r", "25", "-c:v", "libx264",
                "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(temporary)])
            temporary.replace(target)
        finally:
            image.unlink(missing_ok=True)
            temporary.unlink(missing_ok=True)
