import type { Metadata } from 'next';
import './style.css';
export const metadata: Metadata = { title: 'Interlude — Episode Studio', description: 'Semantic scene understanding and safe contextual ad placement for Bengali episodes' };
export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
