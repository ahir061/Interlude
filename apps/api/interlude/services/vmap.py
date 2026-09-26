"""VMAP 1.0 with embedded VAST 3.0; serialized from canonical decisions only."""
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

from interlude.domain import BreakDecision

NS = "http://www.iab.net/videosuite/vmap"
ET.register_namespace("vmap", NS)


def clock_time(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remaining = divmod(milliseconds, 3600000)
    minutes, remaining = divmod(remaining, 60000)
    secs, millis = divmod(remaining, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"


class VMAPSerializer:
    def __init__(self, media_base_url: str = "http://localhost:8000"):
        self.media_base_url = media_base_url

    def serialize(self, decisions: list[BreakDecision]) -> bytes:
        root = ET.Element(f"{{{NS}}}VMAP", version="1.0")
        for d in sorted((d for d in decisions if d.accepted), key=lambda d: d.timestamp_sec):
            slot = ET.SubElement(root, f"{{{NS}}}AdBreak", timeOffset=clock_time(d.timestamp_sec),
                                 breakType="linear", breakId=d.candidate_id)
            source = ET.SubElement(slot, f"{{{NS}}}AdSource", id=d.selected_creative_id,
                                   allowMultipleAds="false", followRedirects="false")
            data = ET.SubElement(source, f"{{{NS}}}VASTAdData")
            vast = ET.SubElement(data, "VAST", version="3.0")
            ad = ET.SubElement(vast, "Ad", id=d.selected_brand_id)
            inline = ET.SubElement(ad, "InLine")
            ET.SubElement(inline, "AdSystem", version="2.0").text = "Interlude"
            ET.SubElement(inline, "AdTitle").text = f"{d.selected_brand_id} / {d.selected_creative_id}"
            ET.SubElement(inline, "Impression").text = urljoin(self.media_base_url, "/health")
            creatives = ET.SubElement(inline, "Creatives")
            creative = ET.SubElement(creatives, "Creative", id=d.selected_creative_id, sequence="1")
            linear = ET.SubElement(creative, "Linear")
            ET.SubElement(linear, "Duration").text = clock_time(d.creative_duration_sec)
            media = ET.SubElement(linear, "MediaFiles")
            dimensions = d.debug.get("creative_dimensions", {})
            ET.SubElement(media, "MediaFile", delivery="progressive", type="video/mp4",
                          width=str(dimensions.get("width") or 640), height=str(dimensions.get("height") or 360),
                          scalable="true", maintainAspectRatio="true").text = urljoin(self.media_base_url, d.creative_url)
        ET.indent(root)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)
