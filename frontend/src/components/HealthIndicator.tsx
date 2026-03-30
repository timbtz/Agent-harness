import { useHealth } from '@/hooks/useProjects';
import { Activity } from 'lucide-react';

export function HealthIndicator() {
  const { data, isLoading } = useHealth();
  const connected = data?.falkordb_connected ?? false;

  return (
    <div className="glass-button flex items-center gap-3 px-4 py-2.5 rounded-full text-sm">
      <div className="relative">
        <Activity className="h-4 w-4 text-muted-foreground" />
        <span
          className={`absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full border border-background ${
            isLoading ? 'bg-muted-foreground animate-pulse' : connected ? 'bg-[hsl(var(--success))]' : 'bg-destructive'
          }`}
        />
      </div>
      <span className="text-muted-foreground">
        {isLoading ? 'Scanning…' : connected ? 'Connected' : 'Offline'}
      </span>
      {data && (
        <span className="ml-auto text-xs text-muted-foreground/50">{data.projects_count} nodes</span>
      )}
    </div>
  );
}
