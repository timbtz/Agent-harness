import { useProjectTimeline } from '@/hooks/useProjectInsights';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';

interface Props {
  projectId: string;
  onSelectEpisode?: (episodeId: string) => void;
}

export function TimelinePanel({ projectId, onSelectEpisode }: Props) {
  const { data, isLoading } = useProjectTimeline(projectId);

  if (isLoading) return <div className="space-y-3">{[1, 2, 3].map(i => <Skeleton key={i} className="h-16 w-full rounded-xl" />)}</div>;

  if (!data?.length) return <p className="text-sm text-muted-foreground text-center py-6 italic">No timeline data yet.</p>;

  return (
    <div className="space-y-1 max-h-[40vh] overflow-y-auto scrollbar-thin">
      {data.map((ep, i) => (
        <div
          key={ep.id}
          onClick={() => onSelectEpisode?.(ep.id)}
          className={`flex gap-3.5 py-2.5 transition-colors ${onSelectEpisode ? 'cursor-pointer hover:bg-card/30 rounded-lg px-1 -mx-1' : ''}`}
        >
          <div className="flex flex-col items-center">
            <div className="h-2.5 w-2.5 rounded-full bg-primary/70 shrink-0 mt-1.5 shadow-sm shadow-primary/20" />
            {i < data.length - 1 && <div className="w-px flex-1 bg-border/30" />}
          </div>
          <div className="flex-1 min-w-0 pb-3">
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="text-[11px] rounded-full capitalize">{ep.category}</Badge>
              <span className="text-xs text-muted-foreground/50">
                {new Date(ep.created_at).toLocaleString()}
              </span>
            </div>
            <p className="text-sm text-muted-foreground mt-1.5 line-clamp-2 leading-relaxed">{ep.content}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
