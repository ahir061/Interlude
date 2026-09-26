from interlude.config import Settings
from interlude.domain import ContextSnapshot, Phase2Semantics, RecentContext
from interlude.services.brands import normalize, negative_match, SENSITIVE_ALIASES


class ContextMemory:
    def __init__(self, settings: Settings, negative_vocabulary: list[str] = ()):
        self.settings = settings
        self.vocabulary = sorted(set(negative_vocabulary) | set(SENSITIVE_ALIASES) | {"death"})
        self.recent: dict[str, tuple[float, bool]] = {}
        self.last_observation: float | None = None
        self.last_failure: float | None = None

    def observe(self, timestamp: float, semantics: Phase2Semantics | None):
        if semantics is None:
            self.last_failure = timestamp
            return
        self.last_observation = timestamp
        # A narrative continuation refreshes prior sensitivity even if the camera hides its source.
        if semantics.sensitive_context_continuing:
            self.recent = {c: (timestamp, True) for c, (seen, _) in self.recent.items()
                           if timestamp - seen <= self.settings.sensitive_context_window_sec}
        observed = [*semantics.sensitive_contexts, *semantics.contexts, *semantics.mood,
                    semantics.narrative_state_before, semantics.narrative_state_after, semantics.dominant_activity]
        sensitive = {normalize(c) for c in semantics.sensitive_contexts}
        sensitive.update(c for c in self.vocabulary if any(negative_match(text, c) for text in observed))
        for context in sensitive:
            self.recent[context] = (timestamp, semantics.sensitive_context_continuing)

    def snapshot(self, timestamp: float, semantics: Phase2Semantics) -> ContextSnapshot:
        recent = [RecentContext(context=c, last_seen_sec=t, distance_sec=timestamp-t, narratively_continuing=continuing)
                  for c, (t, continuing) in sorted(self.recent.items())
                  if 0 <= timestamp-t <= self.settings.sensitive_context_window_sec]
        uncertain = self.last_failure is not None and timestamp-self.last_failure <= self.settings.sensitive_context_window_sec
        if self.last_observation is not None and timestamp-self.last_observation > self.settings.context_freshness_sec:
            uncertain = True
        return ContextSnapshot(current_contexts=semantics.contexts, current_sensitive_contexts=semantics.sensitive_contexts,
                               recent_sensitive_contexts=recent, uncertain=uncertain)
