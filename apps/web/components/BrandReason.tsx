'use client';
import {useEffect,useState} from 'react';
import {request,timecode} from '../lib/api';

type Explanation={brand_id:string;summary:string;source:string;evidence:{timestamp_sec:number;observation:string}[];safety:{verdict:string;confidence:number}[]};
export default function BrandReason({videoId,candidateId}:{videoId:string;candidateId:string}) {
  const [value,setValue]=useState<Explanation|null>(null);
  const [error,setError]=useState('');
  const [attempt,setAttempt]=useState(0);
  useEffect(()=>{
    let cancelled=false;
    setValue(null);setError('');
    void request<Explanation>(`/api/videos/${videoId}/candidates/${candidateId}/explanation`,{method:'POST'})
      .then(result=>{if(!cancelled)setValue(result);})
      .catch(()=>{if(!cancelled)setError('Qwen’s explanation is unavailable. The recorded placement and safety checks are unchanged.');});
    return()=>{cancelled=true;};
  },[videoId,candidateId,attempt]);
  return <section aria-label="Brand selection explanation"><h3>Why this brand?</h3>
    {!value&&!error&&<p role="status">Asking Qwen to explain the recorded match…</p>}
    {error&&<p>{error} <button className="text-button" onClick={()=>setAttempt(x=>x+1)}>Retry explanation</button></p>}
    {value&&<><p><strong>Qwen explanation</strong></p><p data-testid="brand-explanation">{value.summary}</p>
      <small>The engine ranks brands. Qwen summarizes the recorded context and scores.</small>
      <details><summary>Supporting scene observations</summary>{value.evidence.map((e,i)=><p key={i}><strong>{timecode(e.timestamp_sec)}</strong> {e.observation}</p>)}</details>
      {value.safety.map((s,i)=><p key={i}>Independent safety check: {s.verdict} · {Math.round(s.confidence*100)}% confidence</p>)}
    </>}
  </section>;
}
