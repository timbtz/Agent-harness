import { useProjects } from '@/hooks/useProjects';
import { Skeleton } from '@/components/ui/skeleton';
import type { Project } from '@/lib/types';
import { Layers } from 'lucide-react';

interface Props {
  onSelect: (project: Project) => void;
}

export function ProjectList({ onSelect }: Props) {
  const { data: projects, isLoading } = useProjects();

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map(i => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}
      </div>
    );
  }

  if (!projects?.length) {
    return <p className="text-base text-muted-foreground p-6 text-center italic">No projects detected.</p>;
  }

  return (
    <div className="space-y-3">
      {projects.map(p => (
        <button
          key={p.project_id}
          onClick={() => onSelect(p)}
          className="w-full text-left rounded-xl glass-button p-4 group transition-all duration-300"
        >
          <div className="flex items-start justify-between gap-2">
            <span className="font-display font-semibold text-base text-foreground group-hover:text-primary transition-colors">
              {p.name}
            </span>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground/60 bg-secondary/30 px-2.5 py-1 rounded-full">
              <Layers className="h-3 w-3" />
              {p.episode_count}
            </div>
          </div>
          {p.description && (
            <p className="text-sm text-muted-foreground mt-2 line-clamp-2 leading-relaxed">{p.description}</p>
          )}
          <p className="text-xs text-muted-foreground/40 mt-2.5">
            {new Date(p.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
          </p>
        </button>
      ))}
    </div>
  );
}
