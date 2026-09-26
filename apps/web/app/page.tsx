'use client';
import { useEffect, useState } from 'react';
import AdPlayer from '../components/AdPlayer';
import { API, Analysis, Debug, Job, request } from '../lib/api';

export default function Page() {
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [debug, setDebug] = useState<Debug | null>(null);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);

  async function loadResults(video: string) {
    const [a, d] = await Promise.all([request<Analysis>(`/api/videos/${video}/analysis`), request<Debug>(`/api/videos/${video}/debug`)]);
    setAnalysis(a); setDebug(d);
    window.history.replaceState({}, '', `?video=${encodeURIComponent(video)}`);
  }

  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('video');
    if (id) void loadResults(id).catch(e => setError(e.message));
  }, []);

  useEffect(() => {
    if (!job || ['COMPLETED', 'FAILED'].includes(job.status)) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const next = await request<Job>(`/api/jobs/${job.id}`);
        if (cancelled) return;
        setJob(next);
        if (next.status === 'COMPLETED') await loadResults(next.video_id);
        if (next.status === 'FAILED') {
          setError(`${next.error_stage}: ${next.error_code}`);
          setDebug(await request<Debug>(`/api/videos/${next.video_id}/debug`));
        }
      } catch (e) { if (!cancelled) { setError(String(e)); setJob({ ...job }); } }
    }, 1500);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [job]);

  async function analyze() {
    if (!file) return;
    setUploading(true); setError(''); setAnalysis(null); setDebug(null); setJob(null);
    try {
      const form = new FormData(); form.append('file', file);
      const result = await request<{ job: Job }>('/api/videos', { method: 'POST', body: form });
      setJob(result.job);
    } catch (e) { setError(String(e)); } finally { setUploading(false); }
  }
  const busy = uploading || Boolean(job && !['COMPLETED', 'FAILED'].includes(job.status));
  return <main>
    <h1>Interlude</h1>
    <p>Context-aware multimodal ad placement · Phase 1</p>
    <label>Short Bengali video (H.264 MP4, up to 5 minutes)
      <input type="file" accept="video/mp4,.mp4" disabled={busy} onChange={e => setFile(e.target.files?.[0] || null)} />
    </label>
    <button disabled={!file || busy} onClick={() => void analyze()}>{uploading ? 'Uploading…' : 'Analyze'}</button>
    <p role="status">{job ? `Job ${job.id}: ${job.status}` : 'Choose a short clip to begin.'}</p>
    {error && <p role="alert">{error}</p>}
    {analysis && <>
      <h2>Analysis summary</h2>
      <dl>{Object.entries(analysis.summary).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{value}</dd></div>)}</dl>
      {analysis.ad_breaks.length === 0 && <p>No ad break: no candidate satisfied all safety, relevance and pacing requirements.</p>}
      <AdPlayer key={analysis.video.id} source={analysis.video.source_url} breaks={analysis.ad_breaks} />
      <p><a href={`${API}/api/videos/${analysis.video.id}/analysis`} target="_blank" rel="noreferrer">analysis.json</a>{' · '}
        <a href={`${API}/api/videos/${analysis.video.id}/debug`} target="_blank" rel="noreferrer">debug.json</a></p>
    </>}
    {debug && <><h2>Accepted and rejected candidates</h2><table><thead><tr><th>Time</th><th>Decision</th><th>Brand</th><th>WHERE</th><th>Reasons</th></tr></thead>
      <tbody>{debug.decisions.map(d => <tr key={d.candidate_id}><td>{d.timestamp_sec.toFixed(2)}s</td><td>{d.accepted ? 'Accepted' : 'Rejected'}</td>
        <td>{d.selected_brand_id || '—'}</td><td>{d.where_score.toFixed(3)}</td><td>{d.rejection_reasons.join(', ')}</td></tr>)}</tbody></table></>}
    {analysis && <details><summary>Formatted analysis JSON</summary><pre>{JSON.stringify(analysis, null, 2)}</pre></details>}
    {debug && <details><summary>Full debug JSON</summary><pre>{JSON.stringify(debug, null, 2)}</pre></details>}
  </main>;
}
