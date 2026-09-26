from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny, computed_field, model_validator

Score = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]
SafeId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Interval(Model):
    start_sec: Seconds
    end_sec: Seconds

    @model_validator(mode="after")
    def ordered(self):
        if self.end_sec <= self.start_sec:
            raise ValueError("interval end must be after start")
        return self


class Frame(Model):
    timestamp_sec: Seconds
    path: str


class Scene(Interval):
    id: SafeId
    boundary_score: Score = 0
    representative_frames: list[Frame] = Field(default_factory=list)
    shot_ids: list[str] = Field(default_factory=list)
    grouping_reasons: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec


class Word(Interval):
    text: str


class TranscriptSegment(Interval):
    text: str
    words: list[Word] = Field(default_factory=list)


class Transcript(Model):
    language: str = "bn"
    segments: list[TranscriptSegment] = Field(default_factory=list)

    @property
    def speech_words(self) -> list[Word]:
        return [word for segment in self.segments for word in segment.words]

    def around(self, start: float, end: float) -> list[TranscriptSegment]:
        return [s for s in self.segments if s.end_sec >= start and s.start_sec <= end]


class BreakCandidate(Model):
    id: SafeId
    timestamp_sec: Seconds
    preceding_scene_id: SafeId
    following_scene_id: SafeId
    speech_active: bool
    nearest_speech_start_sec: Seconds | None = None
    nearest_speech_end_sec: Seconds | None = None
    silence_before_sec: Seconds
    silence_after_sec: Seconds
    raw_boundary_score: Score
    prefilter_status: Literal["SURVIVED", "REJECTED"]
    rejection_reasons: list[str] = Field(default_factory=list)
    surrounding_shot_sec: Seconds = 0
    dialogue_safety: dict[str, Any] = Field(default_factory=dict)


class SceneSemantics(Model):
    dominant_activity: str = Field(min_length=1)
    contexts: list[str]
    sensitive_contexts: list[str]
    mood: list[str]
    narrative_state_before: str = Field(min_length=1)
    narrative_state_after: str = Field(min_length=1)
    semantic_transition_score: Score
    confidence: Score


class SemanticEvidence(Model):
    timestamp_sec: Seconds
    observation: str = Field(min_length=1)


class Phase2Semantics(SceneSemantics):
    narrative_state: Literal["scene_concluding", "ongoing", "uncertain"]
    dialogue_continuity: Literal["completed", "continuing", "no_dialogue", "uncertain"]
    transition_type: Literal["location_change", "time_change", "activity_change", "narrative_change",
                             "camera_angle", "montage", "none", "uncertain"]
    transition_confidence: Score
    evidence: list[SemanticEvidence] = Field(min_length=1)
    location_before: str = Field(min_length=1)
    location_after: str = Field(min_length=1)
    characters_continuing: bool
    sensitive_context_continuing: bool


class BrandExplanation(Model):
    summary: str = Field(min_length=1, max_length=1200)
    confidence: Score


class SafetyVerdict(Model):
    verdict: Literal["SAFE", "BLOCKED", "UNCERTAIN"]
    confidence: Score
    conflicts: list[str]
    evidence: list[SemanticEvidence] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent(self):
        if self.verdict == "SAFE" and self.conflicts:
            raise ValueError("SAFE cannot include negative conflicts")
        return self


class RecentContext(Model):
    context: str
    last_seen_sec: Seconds
    distance_sec: Seconds
    narratively_continuing: bool


class ContextSnapshot(Model):
    current_contexts: list[str]
    current_sensitive_contexts: list[str]
    recent_sensitive_contexts: list[RecentContext]
    uncertain: bool = False


class BrandEvaluation(Model):
    brand_id: str
    eligible: bool
    hard_blocks: list[str]
    score: Score | None = None
    components: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unranked_if_blocked(self):
        if not self.eligible and self.score is not None:
            raise ValueError("ineligible brands cannot be ranked")
        return self


class Creative(Model):
    creative_id: SafeId = Field(validation_alias="id", serialization_alias="creative_id")
    duration_sec: float = Field(gt=0, le=120, allow_inf_nan=False)
    language: str = "bn"
    url: str = ""
    local_path: str | None = None
    generated: bool = False
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    model_config = ConfigDict(extra="forbid", populate_by_name=True, validate_assignment=True)


class Brand(Model):
    brand_id: SafeId
    display_name: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=200)
    target_contexts: list[str] = Field(default_factory=list)
    negative_contexts: list[str] = Field(default_factory=list)
    creatives: list[Creative] = Field(default_factory=list)


class BrandMatch(Model):
    brand_id: SafeId
    eligible: bool
    hard_block_reasons: list[str] = Field(default_factory=list)
    target_overlap: list[str] = Field(default_factory=list)
    dominant_activity_match: Score = 0
    contextual_score: Score = 0
    category_relevance: Score = 0
    final_score: Score = 0


class BreakDecision(Model):
    candidate_id: SafeId
    timestamp_sec: Seconds
    accepted: bool = False
    rejection_reasons: list[str] = Field(default_factory=list)
    where_score: Score = 0
    whether_pass: bool = False
    selected_brand_id: SafeId | None = None
    selected_creative_id: SafeId | None = None
    creative_url: str | None = None
    creative_duration_sec: Seconds = 0
    brand_match_score: Score = 0
    semantics: SerializeAsAny[SceneSemantics] | None = None
    brand_matches: list[BrandMatch] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def accepted_requires_selection(self):
        if self.accepted and (not self.whether_pass or not self.selected_brand_id or
                              not self.selected_creative_id or not self.creative_url or
                              self.creative_duration_sec <= 0 or self.rejection_reasons):
            raise ValueError("accepted decision requires safe playable selection")
        return self


class VideoMetadata(Model):
    id: str
    duration_sec: float = Field(gt=0, allow_inf_nan=False)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    frame_rate: float = Field(gt=0)
    codec: str
    has_audio: bool
    source_url: str


class AnalysisResult(Model):
    video: VideoMetadata
    scenes: list[Scene]
    transcript: Transcript
    vad_intervals: list[Interval]
    candidates: list[BreakCandidate]
    decisions: list[BreakDecision]
    errors: list[str] = Field(default_factory=list)
    raw_shots: list[Scene] = Field(default_factory=list)
    run_metadata: dict[str, Any] = Field(default_factory=dict)


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    INGESTING = "INGESTING"
    SCENE_DETECTION = "SCENE_DETECTION"
    TRANSCRIBING = "TRANSCRIBING"
    CANDIDATE_GENERATION = "CANDIDATE_GENERATION"
    SEMANTIC_ANALYSIS = "SEMANTIC_ANALYSIS"
    BREAK_OPTIMIZATION = "BREAK_OPTIMIZATION"
    BRAND_MATCHING = "BRAND_MATCHING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AnalysisJob(Model):
    id: str
    video_id: str
    status: JobStatus
    error_code: str | None = None
    error_stage: str | None = None
    state: str = "QUEUED"
    processing_stage: str | None = None
    progress: dict[str, Any] = Field(default_factory=dict)


class AdBreak(Model):
    candidate_id: str
    timestamp_sec: Seconds
    latest_start_sec: Seconds
    brand_id: str
    creative_id: str
    creative_url: str
    duration_sec: Seconds
    where: dict[str, Any]
    whether: dict[str, Any]
    what: dict[str, Any]


class AnalysisManifest(Model):
    video: VideoMetadata
    summary: dict[str, int]
    ad_breaks: list[AdBreak]
