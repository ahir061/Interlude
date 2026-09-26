from xml.etree import ElementTree as ET
from interlude.config import Settings
from interlude.domain import Creative, BreakDecision
from interlude.services.optimizer import GlobalBreakOptimizer, PlacementOption
from interlude.services.vmap import VMAPSerializer, NS


def option(identifier, time, score, duration=6):
    return PlacementOption(identifier, time, "new", 1, score,
                           Creative(creative_id=f"ad_{duration}", duration_sec=duration, url="/api/ads/new/ad"))


def test_global_optimizer_beats_independent_greedy_selection():
    s = Settings(_env_file=None, min_break_gap_sec=30, max_ad_load_percent=30)
    selected, _ = GlobalBreakOptimizer(s).optimize([option("left", 20, 0.7), option("middle", 40, 0.95),
                                                  option("right", 60, 0.7)], 100)
    assert [o.candidate_id for o in selected] == ["left", "right"]


def test_optimizer_selects_feasible_creative_duration():
    s = Settings(_env_file=None, max_ad_load_percent=10)
    selected, _ = GlobalBreakOptimizer(s).optimize([option("slot", 40, 0.9, 30), option("slot", 40, 0.9, 15)], 180)
    assert len(selected) == 1 and selected[0].creative.duration_sec == 15


def test_optimizer_enforces_hourly_cap_gap_and_ad_load():
    s = Settings(_env_file=None, max_breaks_per_hour=2, min_break_gap_sec=30, max_ad_load_percent=10)
    selected, result = GlobalBreakOptimizer(s).optimize([option(str(t), t, 0.8) for t in [10, 20, 40, 80]], 120)
    assert len(selected) == 2 and selected[1].timestamp_sec-selected[0].timestamp_sec >= 30
    assert result["ad_load_percent"] <= 10


def test_vmap_uses_only_accepted_normalized_decisions():
    decisions = [BreakDecision(candidate_id="yes", timestamp_sec=61.234, accepted=True, whether_pass=True,
        selected_brand_id="new", selected_creative_id="creative", creative_url="/api/ads/new/creative",
        creative_duration_sec=6), BreakDecision(candidate_id="no", timestamp_sec=80)]
    root = ET.fromstring(VMAPSerializer().serialize(decisions))
    breaks = root.findall(f"{{{NS}}}AdBreak")
    assert len(breaks) == 1 and breaks[0].attrib["timeOffset"] == "00:01:01.234"
    assert root.find(".//Ad").attrib["id"] == "new"
    assert root.find(".//Creative").attrib["id"] == "creative"
    assert root.find(".//MediaFile").text == "http://localhost:8000/api/ads/new/creative"
