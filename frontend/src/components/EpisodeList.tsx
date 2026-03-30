import { useState } from 'react';
import { useProjectInsights } from '@/hooks/useProjectInsights';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import type { EpisodeCategory } from '@/lib/types';

const CATEGORIES: Array<EpisodeCategory | 'all'> = ['all', 'decision', 'insight', 'error', 'goal', 'architecture'];

const categoryColors: Record<string, string> = {
  decision: 'bg-[hsl(var(--info))]/15 text-[hsl(var(--info))] border-[hsl(var(--info))]/20',
  insight: 'bg-[hsl(var(--success))]/15 text-[hsl(var(--success))] border-[hsl(var(--success))]/20',
  error: 'bg-destructive/15 text-destructive border-destructive/20',
  goal: 'bg-[hsl(var(--warning))]/15 text-[hsl(var(--warning))] border-[hsl(var(--warning))]/20',
  architecture: 'bg-accent/15 text-accent-foreground border-accent/20',
};

interface Props {
  projectId: string;
  onSelectEpisode?: (episodeId: string) => void;
}

export function EpisodeList({ projectId, onSelectEpisode }: Props) {
  const [category, setCategory] = useState<EpisodeCategory | 'all'>('all');
  const { data, isLoading } = useProjectInsights(projectId, category === 'all' ? undefined : category);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-2">
        {CATEGORIES.map(c => (
          <button
            key={c}
            onClick={() => setCategory(c)}
            className={`px-3 py-1.5 text-xs rounded-full border transition-all duration-300 capitalize ${
              category === c
                ? 'glass-button text-primary border-primary/30'
                : 'border-border/30 text-muted-foreground hover:text-foreground hover:border-border/50'
            }`}
          >
            {c === 'all' ? 'All' : c}
          </button>
        ))}
      </div>

      <div className="space-y-2.5 max-h-[40vh] overflow-y-auto scrollbar-thin pr-1">
        {isLoading ? (
          [1, 2, 3].map(i => <Skeleton key={i} className="h-20 w-full rounded-xl" />)
        ) : !data?.episodes?.length ? (
          <p className="text-sm text-muted-foreground text-center py-6 italic">No episodes yet.</p>
        ) : (
          data.episodes.map(ep => (
            <div
              key={ep.id}
              onClick={() => onSelectEpisode?.(ep.id)}
              className={`rounded-xl border border-border/20 bg-card/30 p-3.5 space-y-2 transition-colors ${onSelectEpisode ? 'cursor-pointer hover:bg-card/50 hover:border-border/40' : ''}`}
            >
              <div className="flex items-center gap-2">
                <Badge className={`text-[11px] px-2 py-0.5 rounded-full border capitalize ${categoryColors[ep.category] || ''}`}>
                  {ep.category}
                </Badge>
                <span className="text-xs text-muted-foreground/50 ml-auto">
                  {new Date(ep.created_at).toLocaleDateString()}
                </span>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed line-clamp-2">{ep.content}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
