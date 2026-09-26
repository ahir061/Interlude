from interlude.config import Settings
from interlude.services.scene_builder import SemanticSceneBuilder
from test_phase2_safety import semantics, shots


def test_location_change_splits_scene_even_when_voice_continues():
    scenes=SemanticSceneBuilder(Settings(_env_file=None)).group(shots(),{
        30:semantics(transition_type="location_change",dialogue_continuity="continuing",narrative_state="ongoing")})
    assert len(scenes)==2 and scenes[1].start_sec==30
    assert scenes[1].grouping_reasons[0]=="confirmed_semantic_transition"


def test_angle_change_with_same_activity_stays_same_scene():
    scenes=SemanticSceneBuilder(Settings(_env_file=None)).group(shots(),{
        30:semantics(transition_type="camera_angle",dialogue_continuity="completed")})
    assert len(scenes)==1
