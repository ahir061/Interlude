from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

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


class SceneSemantics(Model):
    dominant_activity: str = Field(min_length=1)
    contexts: list[str]
    sensitive_contexts: list[str]
    mood: list[str]
    narrative_state_before: str = Field(min_length=1)
    narrative_state_after: str = Field(min_length=1)
    semantic_transition_score: Score
    confidence: Score


class Creative(Model):
    creative_id: SafeId = Field(validation_alias="id", serialization_alias="creative_id")
    duration_sec: float = Field(gt=0, le=120, allow_inf_nan=False)
    language: str = "bn"
    url: str = ""
    local_path: str | None = None
    generated: bool = False
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
    semantics: SceneSemantics | None = None
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


class AnalysisJob(Model):
    id: str
    video_id: str
    status: JobStatus
    error_code: str | None = None
    error_stage: str | None = None


class AdBreak(Model):
    candidate_id: str
    timestamp_sec: Seconds
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
