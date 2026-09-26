export type TimedBreak = { candidate_id: string; timestamp_sec: number; latest_start_sec?: number };

export const PREVIEW_LEAD_IN_SEC = 3;

export function previewStart(timestampSec: number): number {
  return Math.max(0, timestampSec - PREVIEW_LEAD_IN_SEC);
}

export function nextBreak<T extends TimedBreak>(previous: number, current: number, breaks: T[], played: Set<string>): T | undefined {
  if (current < previous) return undefined;
  return [...breaks].sort((a, b) => a.timestamp_sec - b.timestamp_sec).find(
    b => !played.has(b.candidate_id) && previous < b.timestamp_sec && current >= b.timestamp_sec
      && current <= (b.latest_start_sec ?? b.timestamp_sec + 0.25)
  );
}

export function skippedBySeek(previous: number, current: number, breaks: TimedBreak[]): string[] {
  return breaks.filter(b => b.timestamp_sec > previous && b.timestamp_sec <= current).map(b => b.candidate_id);
}
