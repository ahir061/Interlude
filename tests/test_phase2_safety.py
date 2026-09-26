import pytest
from interlude.config import Settings
from interlude.domain import Phase2Semantics, Scene, Transcript, TranscriptSegment, Interval, Brand
from interlude.services.scene_builder import SemanticSceneBuilder, DialogueSafetyGate
from interlude.services.context import ContextMemory
from interlude.services.brand_policy import BrandEligibilityEngine, BrandRankingEngine


def semantics(**changes):
    return Phase2Semantics(**(dict(dominant_activity="cooking", contexts=["cooking"], sensitive_contexts=[], mood=[],
        narrative_state_before="cooking finishes", narrative_state_after="people leave",
        semantic_transition_score=0.9, confidence=0.95, narrative_state="scene_concluding",
        dialogue_continuity="completed", transition_type="location_change", transition_confidence=0.95,
        evidence=[{"timestamp_sec": 30, "observation": "conversation ends and location changes"}],
        location_before="kitchen", location_after="outside", characters_continuing=False,
        sensitive_context_continuing=False) | changes))


def shots():
    return [Scene(id=f"shot_{i}", start_sec=i*30, end_sec=(i+1)*30, boundary_score=0.9) for i in range(3)]


def test_camera_angle_switch_is_one_conversation_scene():
    scenes = SemanticSceneBuilder(Settings(_env_file=None)).group(shots(), {
        30: semantics(transition_type="camera_angle", dialogue_continuity="continuing"),
        60: semantics(transition_type="camera_angle", dialogue_continuity="continuing")})
    assert len(scenes) == 1 and len(scenes[0].shot_ids) == 3


def test_completed_dialogue_location_transition_creates_scene():
    scenes = SemanticSceneBuilder(Settings(_env_file=None)).group(shots(), {30: semantics()})
    assert len(scenes) == 2 and scenes[1].start_sec == 30


def test_rapid_montage_does_not_create_many_breaks():
    assert len(SemanticSceneBuilder(Settings(_env_file=None)).group(shots(), {
        30: semantics(transition_type="montage"), 60: semantics(transition_type="montage")})) == 1


def test_semantic_continuation_does_not_override_exact_speech_timeline():
    transcript = Transcript(segments=[TranscriptSegment(start_sec=20, end_sec=29, text="Where are you—"),
                                      TranscriptSegment(start_sec=31, end_sec=35, text="—going?")])
    result = DialogueSafetyGate(Settings(_env_file=None)).evaluate(30, transcript, [], 90,
        semantics(dialogue_continuity="continuing"))
    assert result["safe"] and result["semantic_dialogue_continuity"] == "continuing"


def test_asr_vad_disagreement_is_unsafe():
    result = DialogueSafetyGate(Settings(_env_file=None)).evaluate(30, Transcript(),
        [Interval(start_sec=29, end_sec=31)], 90, semantics())
    assert not result["safe"] and result["vad_region_crossing_boundary"]


@pytest.mark.parametrize("context,category", [("funeral", "food"), ("grief", "food"),
    ("accident", "automotive"), ("hospital", "travel")])
def test_sensitive_context_carries_into_next_scene(context, category):
    s = Settings(_env_file=None)
    memory = ContextMemory(s)
    memory.observe(30, semantics(sensitive_contexts=[context]))
    current = semantics(dominant_activity="walking", contexts=["family", "walking"])
    snapshot = memory.snapshot(45, current)
    brand = Brand(brand_id="new", display_name="New", category=category, target_contexts=["family"],
                  negative_contexts=[context])
    result = BrandEligibilityEngine().evaluate(current, snapshot, [brand])[0]
    assert not result.eligible and result.score is None
    assert snapshot.recent_sensitive_contexts[0].distance_sec == 15


def test_narrative_carryover_outlives_temporal_window():
    memory = ContextMemory(Settings(_env_file=None, sensitive_context_window_sec=10))
    memory.observe(10, semantics(sensitive_contexts=["grief"]))
    memory.observe(18, semantics(sensitive_context_continuing=True))
    assert memory.snapshot(25, semantics(sensitive_context_continuing=True)).recent_sensitive_contexts


@pytest.mark.parametrize("expired", [False, True])
def test_unresolved_continuing_sensitivity_blocks_brands_and_carries_forward(expired):
    memory = ContextMemory(Settings(_env_file=None, sensitive_context_window_sec=10))
    if expired:
        memory.observe(1, semantics(sensitive_contexts=["grief"]))
    current = semantics(sensitive_context_continuing=True)
    memory.observe(30, current)
    brand = Brand(brand_id="food", display_name="Food", category="food", negative_contexts=["funeral"])
    result = BrandEligibilityEngine().evaluate(current, memory.snapshot(30, current), [brand])[0]
    assert not result.eligible and result.score is None
    memory.observe(35, semantics())
    assert memory.snapshot(35, semantics()).uncertain


def test_driving_dominates_secondary_phone_context():
    s = Settings(_env_file=None)
    scene = semantics(dominant_activity="driving", contexts=["phone", "family conversation", "travel"])
    brands = [Brand(brand_id="auto", display_name="Auto", category="automotive", target_contexts=["driving"]),
              Brand(brand_id="phone", display_name="Phone", category="telecom", target_contexts=["phone", "family conversation", "travel"])]
    snapshot = ContextMemory(s).snapshot(30, scene)
    ranked = BrandRankingEngine(s).rank(scene, brands, BrandEligibilityEngine().evaluate(scene, snapshot, brands))
    assert ranked[0].brand_id == "auto"


@pytest.mark.parametrize("activity,category", [("video call", "telecom"), ("shopping", "ecommerce"), ("payment", "fintech")])
def test_dominant_activity_is_strongly_relevant(activity, category):
    s = Settings(_env_file=None)
    scene = semantics(dominant_activity=activity, contexts=[activity])
    brands = [Brand(brand_id="new", display_name="New", category=category, target_contexts=[activity])]
    snapshot = ContextMemory(s).snapshot(30, scene)
    ranked = BrandRankingEngine(s).rank(scene, brands, BrandEligibilityEngine().evaluate(scene, snapshot, brands))
    assert ranked[0].score >= 0.6


def test_relevance_uncertainty_reduces_score_without_eliminating_brand():
    s = Settings(_env_file=None)
    brand = Brand(brand_id="food", display_name="Food", category="food", target_contexts=["cooking"])
    scores = []
    for confidence in (0.95, 0.55):
        scene = semantics(confidence=confidence)
        memory = ContextMemory(s)
        memory.observe(30, scene)
        eligible = BrandEligibilityEngine().evaluate(scene, memory.snapshot(30, scene), [brand])
        ranked = BrandRankingEngine(s).rank(scene, [brand], eligible)
        assert ranked[0].eligible
        scores.append(ranked[0].score)
    assert 0 < scores[1] < scores[0]


def test_negative_conflict_blocks_brand_not_every_other_brand():
    s = Settings(_env_file=None)
    scene = semantics(sensitive_contexts=["grief"])
    memory = ContextMemory(s)
    memory.observe(30, scene)
    brands = [Brand(brand_id="food", display_name="Food", category="food", negative_contexts=["grief"]),
              Brand(brand_id="phone", display_name="Phone", category="telecom", negative_contexts=["violence"])]
    results = BrandEligibilityEngine().evaluate(scene, memory.snapshot(30, scene), brands)
    assert not results[0].eligible and results[0].hard_blocks == ["grief"]
    assert results[1].eligible


def test_dominant_action_beats_incidental_scenery_with_unseen_brand():
    s = Settings(_env_file=None)
    brands = [Brand(brand_id='unseen_food', display_name='Synthetic Food', category='food', target_contexts=['cooking']),
              Brand(brand_id='unseen_travel', display_name='Synthetic Travel', category='travel', target_contexts=['mountains', 'resort'])]
    scene = semantics(dominant_activity='Serving tea and socializing in a mountain resort setting', contexts=['food', 'resort', 'mountains'])
    eligible = BrandEligibilityEngine().evaluate(scene, ContextMemory(s).snapshot(30, scene), brands)
    assert BrandRankingEngine(s).rank(scene, brands, eligible)[0].brand_id == 'unseen_food'
    blocked = scene.model_copy(update={'sensitive_contexts': ['funeral']})
    brands[0].negative_contexts = ['funeral']
    eligible = BrandEligibilityEngine().evaluate(blocked, ContextMemory(s).snapshot(30, blocked), brands)
    assert not next(x for x in eligible if x.brand_id == 'unseen_food').eligible
