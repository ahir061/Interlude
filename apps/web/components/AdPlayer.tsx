'use client';
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { API, AdBreak } from '../lib/api';
import { nextBreak, previewStart, skippedBySeek } from '../lib/playback';

export type AdPlayerHandle = { preview: (candidateId: string) => void };
const AdPlayer = forwardRef<AdPlayerHandle, { source: string; breaks: AdBreak[] }>(function AdPlayer({ source, breaks }, ref) {
  const content = useRef<HTMLVideoElement>(null);
  const ad = useRef<HTMLVideoElement>(null);
  const played = useRef(new Set<string>());
  const previous = useRef(0);
  const resume = useRef(0);
  const activeRef = useRef<AdBreak | null>(null);
  const previewTarget = useRef<AdBreak | null>(null);
  const previewSeeking = useRef(false);
  const previewFrame = useRef<number | null>(null);
  const seeking = useRef(false);
  const [active, setActive] = useState<AdBreak | null>(null);
  const [message, setMessage] = useState('Ready to play content');
  const [error, setError] = useState('');
  const [adNeedsPlay, setAdNeedsPlay] = useState(false);

  useImperativeHandle(ref, () => ({ preview(candidateId) {
    const slot = breaks.find(item => item.candidate_id === candidateId);
    if (!slot || !content.current) return;
    const video = content.current;
    video.pause();
    ad.current?.pause();
    if (previewFrame.current !== null) cancelAnimationFrame(previewFrame.current);
    previewFrame.current = null;
    previewTarget.current = slot;
    played.current.delete(slot.candidate_id);
    resume.current = slot.timestamp_sec;
    const start = previewStart(slot.timestamp_sec);
    previous.current = start;
    activeRef.current = null;
    setError('');
    setAdNeedsPlay(false);
    setActive(null);
    setMessage(`Playing episode from ${start.toFixed(3)} seconds to the break at ${slot.timestamp_sec.toFixed(3)} seconds`);
    previewSeeking.current = Math.abs(video.currentTime - start) > 0.05;
    seeking.current = previewSeeking.current;
    if (previewSeeking.current) video.currentTime = start;
    if (!previewSeeking.current) seeking.current = false;
    void video.play().catch(() => setError('Press play to watch the lead-in.'));
  }}), [breaks]);

  useEffect(() => () => {
    if (previewFrame.current !== null) cancelAnimationFrame(previewFrame.current);
  }, []);

  useEffect(() => {
    if (!active || !ad.current) return;
    // Preserve user audio preferences across the two media elements.
    if (content.current) {
      ad.current.muted = content.current.muted;
      ad.current.volume = content.current.volume;
    }
    ad.current.currentTime = 0;
    void ad.current.play().catch(() => setAdNeedsPlay(true));
  }, [active]);

  function resumeContent() {
    if (!content.current) return;
    ad.current?.pause();
    activeRef.current = null;
    previewTarget.current = null;
    setActive(null);
    setAdNeedsPlay(false);
    setError('');
    content.current.currentTime = resume.current;
    previous.current = resume.current;
    setMessage(`Content resumed at ${resume.current.toFixed(3)} seconds`);
    void content.current.play().catch(() => setError('Press play to resume content.'));
  }

  function tick() {
    const video = content.current;
    if (!video || activeRef.current || seeking.current || video.seeking || video.paused) return;
    const preview = previewTarget.current;
    if (preview) {
      if (video.currentTime < preview.timestamp_sec) return;
      previewTarget.current = null;
      if (previewFrame.current !== null) cancelAnimationFrame(previewFrame.current);
      previewFrame.current = null;
      played.current.add(preview.candidate_id);
      resume.current = preview.timestamp_sec;
      previous.current = preview.timestamp_sec;
      video.pause();
      activeRef.current = preview;
      setActive({...preview});
      setMessage(`Advertisement: ${preview.brand_id} · resume at ${resume.current.toFixed(3)} seconds`);
      return;
    }
    const slot = nextBreak(previous.current, video.currentTime, breaks, played.current);
    previous.current = video.currentTime;
    if (!slot) return;
    played.current.add(slot.candidate_id);
    resume.current = video.currentTime;
    video.pause();
    activeRef.current = slot;
    setActive(slot);
    setMessage(`Advertisement: ${slot.brand_id} · resume at ${resume.current.toFixed(3)} seconds`);
  }

  function watchPreview() {
    if (!previewTarget.current || !content.current || content.current.paused) return;
    tick();
    if (previewTarget.current) previewFrame.current = requestAnimationFrame(watchPreview);
  }

  return <section aria-label="Content and advertisement player">
    <h2>Episode playback</h2>
    <p role="status" data-testid="player-status">{message}</p>
    <video ref={content} data-testid="content-video" src={API + source} controls playsInline preload="metadata"
      hidden={Boolean(active)} onTimeUpdate={tick}
      onPlaying={() => {
        if (previewFrame.current !== null) cancelAnimationFrame(previewFrame.current);
        watchPreview();
      }}
      onSeeking={() => {
        seeking.current = true;
        if (previewTarget.current && !previewSeeking.current) {
          previewTarget.current = null;
          if (previewFrame.current !== null) cancelAnimationFrame(previewFrame.current);
          previewFrame.current = null;
          setMessage('Preview cancelled after seeking. Ready to play content.');
        }
      }}
      onSeeked={() => {
        if (!content.current) return;
        if (!previewSeeking.current) skippedBySeek(previous.current, content.current.currentTime, breaks).forEach(id => played.current.add(id));
        previewSeeking.current = false;
        previous.current = content.current.currentTime;
        seeking.current = false;
      }}
      onError={() => setError('The source video could not be loaded.')}
    />
    {active && <video ref={ad} data-testid="ad-video" src={API + active.creative_url} playsInline preload="auto"
      onEnded={resumeContent} onError={() => setError('Advertisement failed to load. Resume content below.')} />}
    {adNeedsPlay && <button onClick={() => { void ad.current?.play().then(() => setAdNeedsPlay(false)); }}>Play advertisement</button>}
    {error && <p role="alert">{error} {active && <button onClick={resumeContent}>Resume content</button>}</p>}
    <p>Seeking forward skips crossed breaks. Automatic breaks play once. Schedule clicks play three seconds of the episode before the selected advertisement.</p>
  </section>;
});
export default AdPlayer;
