export const API = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
export type AdBreak = { candidate_id: string; timestamp_sec: number; brand_id: string; creative_id: string; creative_url: string; duration_sec: number };
export type Analysis = { video: { id: string; source_url: string; duration_sec: number }; summary: Record<string, number>; ad_breaks: AdBreak[] };
export type Job = { id: string; video_id: string; status: string; error_code?: string; error_stage?: string };
export type Decision = { candidate_id: string; timestamp_sec: number; accepted: boolean; rejection_reasons: string[]; selected_brand_id: string | null; where_score: number };
export type Debug = { decisions: Decision[] };

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API + path, { ...init, cache: 'no-store' });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}
