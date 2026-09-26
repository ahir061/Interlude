from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", case_sensitive=False, hide_input_in_errors=True)
    llm_api_url: str = Field(default="", repr=False)
    llm_model: str = ""
    llm_api_key: SecretStr = SecretStr("")
    db_host: str = Field(default="", repr=False)
    db_port: int = 3306
    db_user: str = Field(default="", repr=False)
    db_password: SecretStr = SecretStr("")
    db_name: str = Field(default="", repr=False)
    groq_api_key: SecretStr = SecretStr("")
    asr_model: Literal["whisper-large-v3"] = "whisper-large-v3"
    asr_language: Literal["bn"] = "bn"
    asr_response_format: Literal["verbose_json"] = "verbose_json"
    asr_temperature: float = Field(default=0, ge=0, le=0)
    asr_word_timestamps: bool = True
    asr_segment_timestamps: bool = True
    asr_request_timeout_sec: float = Field(default=180, gt=0)
    asr_max_retries: int = Field(default=3, ge=0, le=5)
    llm_request_timeout_sec: float = Field(default=120, gt=0)
    llm_max_retries: int = Field(default=3, ge=0, le=5)
    llm_json_mode: bool = True
    llm_enable_thinking: bool = False
    llm_max_tokens: int = Field(default=1200, ge=256, le=16384)
    brands_path: Path = ROOT / "content-sample-assets-folder/brands.json"
    data_dir: Path = ROOT / "data"
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    max_breaks_per_hour: int = Field(default=12, ge=0)
    min_break_gap_sec: float = Field(default=30, ge=0)
    max_ad_load_percent: float = Field(default=10, ge=0, le=100)
    # Legacy Phase 1 compatibility; no Phase 2 silence/shot/edge vetoes.
    min_dialogue_gap_sec: float = Field(default=0.5, ge=0.1)
    min_scene_sec: float = Field(default=2, ge=0.1)
    min_edge_gap_sec: float = Field(default=10, ge=0)
    min_where_score: float = Field(default=0.55, ge=0, le=1)
    min_semantic_confidence: float = Field(default=0.7, ge=0, le=1)
    min_brand_score: float = Field(default=0.15, ge=0, le=1)
    where_boundary_weight: float = Field(default=0.25, ge=0)
    where_dialogue_weight: float = Field(default=0.2, ge=0)
    # Legacy setting; nearby gap now has a single dialogue-gap weight.
    where_silence_weight: float = Field(default=0.2, ge=0)
    where_semantic_weight: float = Field(default=0.2, ge=0)
    where_closure_weight: float = Field(default=0.2, ge=0)
    where_stability_weight: float = Field(default=0.1, ge=0)
    where_confidence_weight: float = Field(default=0.05, ge=0)
    scene_threshold: float = Field(default=27, gt=0)
    max_upload_mb: int = Field(default=250, gt=0)
    max_video_duration_sec: float = Field(default=300, gt=0)
    cors_origins: list[str] = ["http://localhost:3000"]
    worker_lease_sec: int = Field(default=900, ge=300)
    # Deprecated silence gates, retained for configuration compatibility only.
    min_pre_cut_silence_ms: int = Field(default=500, ge=100)
    min_post_cut_silence_ms: int = Field(default=500, ge=100)
    # Semantic scene grouping only, never ad-slot eligibility.
    min_transition_confidence: float = Field(default=0.8, ge=0, le=1)
    min_transition_score: float = Field(default=0.65, ge=0, le=1)
    sensitive_context_window_sec: float = Field(default=90, ge=0)
    context_sample_interval_sec: float = Field(default=20, gt=0, le=30)
    context_freshness_sec: float = Field(default=30, gt=0)
    brand_activity_weight: float = Field(default=0.6, gt=0)
    brand_target_weight: float = Field(default=0.25, ge=0)
    brand_category_weight: float = Field(default=0.1, ge=0)
    brand_secondary_weight: float = Field(default=0.05, ge=0)
    safety_min_confidence: float = Field(default=0.9, ge=0, le=1)
    optimizer_beam_width: int = Field(default=2048, ge=1, le=100000)
    semantic_cache_enabled: bool = True
    reports_dir: Path = ROOT / "reports"
    upload_retention_hours: float = Field(default=72, ge=1)
    work_retention_hours: float = Field(default=24, ge=1)
    worker_heartbeat_sec: int = Field(default=15, ge=1)
    media_base_url: str = "http://localhost:8000"

    @model_validator(mode="after")
    def validate_weights(self):
        if not self.asr_segment_timestamps:
            raise ValueError("ASR segment timestamps are required for dialogue safety")
        if sum(self.weights.values()) <= 0:
            raise ValueError("WHERE weights must have positive sum")
        if self.brand_activity_weight <= sum((self.brand_target_weight, self.brand_category_weight,
                                               self.brand_secondary_weight)):
            raise ValueError("dominant activity weight must exceed all secondary weights combined")
        if self.worker_heartbeat_sec >= self.worker_lease_sec / 3:
            raise ValueError("heartbeat must be less than one third of lease")
        return self

    @property
    def weights(self) -> dict[str, float]:
        return {"visual": self.where_boundary_weight, "dialogue_gap": self.where_dialogue_weight,
                "semantic_transition": self.where_semantic_weight, "narrative_closure": self.where_closure_weight,
                "shot_stability": self.where_stability_weight, "confidence": self.where_confidence_weight}

    def database_url(self) -> URL:
        return URL.create("mysql+pymysql", username=self.db_user, password=self.db_password.get_secret_value(),
                          host=self.db_host, port=self.db_port, database=self.db_name,
                          query={"charset": "utf8mb4"})

    def prepare_dirs(self):
        for name in ("uploads", "work", "ads", "outputs", "semantic_cache"):
            (self.data_dir / name).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
