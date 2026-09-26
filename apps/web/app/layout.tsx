import type { Metadata } from 'next';
import './style.css';
export const metadata: Metadata = { title: 'Interlude — Phase 1', description: 'Context-aware ad placement demo' };
export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
