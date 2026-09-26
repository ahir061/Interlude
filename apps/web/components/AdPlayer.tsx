'use client';
import { useEffect, useRef, useState } from 'react';
import { API, AdBreak } from '../lib/api';
import { nextBreak, skippedBySeek } from '../lib/playback';

export default function AdPlayer({ source, breaks }: { source: string; breaks: AdBreak[] }) {
  const content = useRef<HTMLVideoElement>(null);
  const ad = useRef<HTMLVideoElement>(null);
  const played = useRef(new Set<string>());
  const previous = useRef(0);
  const resume = useRef(0);
  const activeRef = useRef<AdBreak | null>(null);
  const seeking = useRef(false);
  const [active, setActive] = useState<AdBreak | null>(null);
  const [message, setMessage] = useState('Ready to play content');
  const [error, setError] = useState('');
  const [adNeedsPlay, setAdNeedsPlay] = useState(false);

  useEffect(() => {
    if (!active || !ad.current) return;
    // Preserve user audio preferences across the two media elements.
    if (content.current) {
      ad.current.muted = content.current.muted;
      ad.current.volume = content.current.volume;
    }
    void ad.current.play().catch(() => setAdNeedsPlay(true));
  }, [active]);

  function resumeContent() {
    if (!content.current) return;
    ad.current?.pause();
    activeRef.current = null;
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

  return <section aria-label="Content and advertisement player">
    <h2>Playback demo</h2>
    <p role="status" data-testid="player-status">{message}</p>
    <video ref={content} data-testid="content-video" src={API + source} controls playsInline preload="metadata"
      hidden={Boolean(active)} onTimeUpdate={tick}
      onSeeking={() => { seeking.current = true; }}
      onSeeked={() => {
        if (!content.current) return;
        skippedBySeek(previous.current, content.current.currentTime, breaks).forEach(id => played.current.add(id));
        previous.current = content.current.currentTime;
        seeking.current = false;
      }}
      onError={() => setError('The source video could not be loaded.')}
    />
    {active && <video ref={ad} data-testid="ad-video" src={API + active.creative_url} playsInline preload="auto"
      onEnded={resumeContent} onError={() => setError('Advertisement failed to load. Resume content below.')} />}
    {adNeedsPlay && <button onClick={() => { void ad.current?.play().then(() => setAdNeedsPlay(false)); }}>Play advertisement</button>}
    {error && <p role="alert">{error} {active && <button onClick={resumeContent}>Resume content</button>}</p>}
    <p>Seeking forward skips crossed breaks. Each break plays at most once in this player session.</p>
  </section>;
}
