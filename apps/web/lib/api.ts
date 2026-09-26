export const API = process.env.NEXT_PUBLIC_API_BASE ?? '';
export type AdBreak = { candidate_id: string; timestamp_sec: number; latest_start_sec: number; brand_id: string; creative_id: string; creative_url: string; duration_sec: number };
export type Analysis = { video: { id: string; source_url: string; duration_sec: number }; summary: Record<string, number>; ad_breaks: AdBreak[] };
export type Job = { id: string; video_id: string; status: string; error_code?: string; error_stage?: string; progress?: {stage?: string; completed?: number; total?: number} };
export type Decision = { candidate_id: string; timestamp_sec: number; accepted: boolean; rejection_reasons: string[]; selected_brand_id: string | null; where_score: number; debug?: {rank?: number; hard_blocked?: boolean; where?: {components?: Record<string,number>;sequence_interruption_penalty?:number}; brands?: {brand_id:string;eligible:boolean;score:number|null;hard_blocks:string[]}[]}; semantics?: {dominant_activity:string;contexts:string[]} };
export type Scene = {id:string;start_sec:number;end_sec:number;shot_ids:string[];grouping_reasons:string[]};
export type Debug = { decisions: Decision[]; scenes?:Scene[]; raw_shots?:Scene[]; run_metadata?:Record<string,unknown> };
export type Episode = {id:string;metadata:{filename?:string;duration_sec:number;size_bytes?:number};created_at:string;media_available:boolean;job:Job|null};
export type Brand = {brand_id:string;display_name:string;category:string;target_contexts:string[];negative_contexts:string[]};
export type Config = {max_upload_mb:number;max_video_duration_sec:number;protected:boolean};

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API + path, { ...init, credentials:'include', headers:{'X-Interlude-Request':'1',...init?.headers}, cache: 'no-store' });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function uploadEpisode(file:File,onProgress:(percent:number)=>void,signal?:AbortSignal):Promise<{job:Job}> {
  return new Promise((resolve,reject)=>{
    const xhr=new XMLHttpRequest();
    xhr.open('POST',API+'/api/videos'); xhr.withCredentials=true;
    xhr.setRequestHeader('X-Interlude-Request','1');
    xhr.upload.onprogress=e=>{if(e.lengthComputable)onProgress(Math.round(e.loaded/e.total*100));};
    xhr.onerror=()=>reject(new Error('Upload connection failed. Please retry.'));
    xhr.onabort=()=>reject(new Error('Upload cancelled.'));
    xhr.onload=()=>{try{const data=JSON.parse(xhr.responseText);if(xhr.status>=400)reject(new Error(data.detail||'Upload failed'));else resolve(data);}catch{reject(new Error('Unexpected upload response.'));}};
    signal?.addEventListener('abort',()=>xhr.abort(),{once:true});
    const form=new FormData();form.append('file',file);xhr.send(form);
  });
}

export function timecode(seconds:number){const value=Math.max(0,Math.floor(seconds));return `${Math.floor(value/3600)>0?`${Math.floor(value/3600)}:`:''}${String(Math.floor(value/60)%60).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`;}
