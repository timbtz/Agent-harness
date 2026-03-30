import { useState } from 'react';
import { X, ArrowRight, ArrowLeft, Circle, Trash2, AlertTriangle } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { CATEGORY_COLORS } from '@/lib/colors';

interface ConnectedEdge {
  id?: string;
  source: string;
  target: string;
  fact: string;
  type: string;
  sourceName: string;
  targetName: string;
  direction: 'incoming' | 'outgoing';
}

interface Props {
  node: { id: string; name: string; summary?: string; node_type?: string; category?: string };
  edges: ConnectedEdge[];
  onClose: () => void;
  onDeleteNode?: (nodeId: string) => void;
  onNavigateToNode?: (nodeId: string) => void;
}

function toTitleCase(s: string) {
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export function NodeDetailPanel({ node, edges, onClose, onDeleteNode, onNavigateToNode }: Props) {
  const outgoing = edges.filter(e => e.direction === 'outgoing');
  const incoming = edges.filter(e => e.direction === 'incoming');
  const [showConfirm, setShowConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const isEpisodic = node.node_type === 'episodic';
  const nodeColor = isEpisodic
    ? (CATEGORY_COLORS[node.category ?? ''] ?? '#888888')
    : 'hsl(var(--primary))';
  const displayName = isEpisodic
    ? `[${(node.category ?? 'episode').toUpperCase()}]`
    : node.name;

  const handleDelete = async () => {
    setDeleting(true);
    onDeleteNode?.(node.id);
    setShowConfirm(false);
    setDeleting(false);
  };

  return (
    <>
      <div className="absolute top-4 right-4 w-80 max-h-[calc(100vh-6rem)] glass border border-border/20 rounded-2xl shadow-2xl shadow-primary/5 z-50 flex flex-col">
        {/* Header */}
        <div className="p-5 border-b border-border/15 shrink-0">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2.5">
              <Circle className="h-3 w-3" style={{ color: nodeColor, fill: nodeColor }} />
              <h3 className="text-base font-display font-semibold text-foreground">{displayName}</h3>
            </div>
            <button onClick={onClose} className="glass-button p-1.5 rounded-full text-muted-foreground hover:text-foreground transition-colors">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          {node.summary && (
            <p className="text-sm text-muted-foreground mt-2.5 leading-relaxed">{node.summary}</p>
          )}
        </div>

        {/* Edges */}
        <ScrollArea className="flex-1 scrollbar-thin">
          <div className="p-5 space-y-5">
            {outgoing.length > 0 && (
              <div className="space-y-2.5">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/60 flex items-center gap-2">
                  <ArrowRight className="h-3 w-3" />
                  Outgoing ({outgoing.length})
                </p>
                {outgoing.map((e, i) => (
                  <div key={`out-${i}`} className="p-3.5 rounded-xl bg-secondary/15 border border-border/15 space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="glass-button px-2.5 py-1 text-primary text-xs rounded-full">
                        {toTitleCase(e.type)}
                      </span>
                      <span className="text-xs text-muted-foreground/40">→</span>
                      <button
                        onClick={() => onNavigateToNode?.(e.target)}
                        className={`text-sm font-display truncate text-left transition-colors ${onNavigateToNode ? 'text-foreground hover:text-primary cursor-pointer underline-offset-2 hover:underline' : 'text-foreground'}`}
                      >
                        {e.targetName}
                      </button>
                    </div>
                    <p className="text-sm text-muted-foreground leading-relaxed">{e.fact}</p>
                  </div>
                ))}
              </div>
            )}

            {incoming.length > 0 && (
              <div className="space-y-2.5">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/60 flex items-center gap-2">
                  <ArrowLeft className="h-3 w-3" />
                  Incoming ({incoming.length})
                </p>
                {incoming.map((e, i) => (
                  <div key={`in-${i}`} className="p-3.5 rounded-xl bg-secondary/15 border border-border/15 space-y-2">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => onNavigateToNode?.(e.source)}
                        className={`text-sm font-display truncate text-left transition-colors ${onNavigateToNode ? 'text-foreground hover:text-primary cursor-pointer underline-offset-2 hover:underline' : 'text-foreground'}`}
                      >
                        {e.sourceName}
                      </button>
                      <span className="text-xs text-muted-foreground/40">→</span>
                      <span className="glass-button px-2.5 py-1 text-accent-foreground text-xs rounded-full">
                        {toTitleCase(e.type)}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground leading-relaxed">{e.fact}</p>
                  </div>
                ))}
              </div>
            )}

            {edges.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-6 italic">No connections.</p>
            )}
          </div>
        </ScrollArea>

        {/* Delete */}
        {onDeleteNode && (
          <div className="p-5 border-t border-border/15 shrink-0 space-y-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground/50">
              <AlertTriangle className="h-3 w-3" />
              <span>Deleting this node also removes all its edges.</span>
            </div>
            <button
              onClick={() => setShowConfirm(true)}
              className="w-full glass-button flex items-center justify-center gap-2 px-4 py-2.5 rounded-full text-destructive text-sm hover:bg-destructive/10 transition-colors"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete Node
            </button>
          </div>
        )}
      </div>

      <AlertDialog open={showConfirm} onOpenChange={setShowConfirm}>
        <AlertDialogContent className="glass border-border/20 rounded-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-foreground font-display text-lg">Delete "{displayName}"?</AlertDialogTitle>
            <AlertDialogDescription className="text-sm leading-relaxed">
              This will permanently remove this node and all {edges.length} connected edge{edges.length !== 1 ? 's' : ''}.
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="glass-button rounded-full text-sm">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90 rounded-full text-sm"
            >
              {deleting ? 'Deleting…' : 'Delete Node'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
