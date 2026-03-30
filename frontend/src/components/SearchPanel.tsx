import { useState } from 'react';
import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useSearchProject } from '@/hooks/useProjectInsights';

interface Props {
  projectId: string;
  onSelectResult?: (entityName: string) => void;
}

export function SearchPanel({ projectId, onSelectResult }: Props) {
  const [query, setQuery] = useState('');
  const search = useSearchProject(projectId);

  const handleSearch = () => {
    if (!query.trim()) return;
    search.mutate({ query: query.trim(), limit: 10 });
  };

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search className="absolute left-3.5 top-3 h-4 w-4 text-muted-foreground/50" />
        <Input
          placeholder="Search episodes…"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          className="pl-10 h-11 text-sm bg-secondary/30 border-border/20 rounded-xl placeholder:text-muted-foreground/40 focus:border-primary/30"
        />
      </div>

      {search.isPending && <p className="text-sm text-muted-foreground animate-pulse italic">Searching…</p>}

      {search.data && (
        <div className="space-y-2.5 max-h-[30vh] overflow-y-auto scrollbar-thin">
          {search.data.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4 italic">No results found.</p>
          ) : (
            search.data.map(ep => (
              <div
                key={ep.id}
                onClick={() => onSelectResult?.(ep.id)}
                className={`rounded-xl border border-border/20 bg-card/30 p-3.5 space-y-2 transition-colors ${onSelectResult ? 'cursor-pointer hover:bg-card/50 hover:border-border/40' : ''}`}
              >
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-[11px] rounded-full capitalize">{ep.category}</Badge>
                </div>
                <p className="text-sm text-muted-foreground line-clamp-3 leading-relaxed">{ep.content}</p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
