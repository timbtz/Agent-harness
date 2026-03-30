import { useState } from 'react';
import { X, ArrowRight, Zap, Clock, AlertTriangle, Trash2, Ban } from 'lucide-react';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import type { GraphEdge } from '@/lib/types';

interface Props {
  edge: GraphEdge & { sourceName?: string; targetName?: string };
  onClose: () => void;
  onDeleteEdge?: (edgeId: string) => void;
}

function timeAgo(iso?: string): string {
  if (!iso) return 'unknown';
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (days === 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 30) return `${days} days ago`;
  if (days < 365) return `${Math.floor(days / 30)} months ago`;
  return `${Math.floor(days / 365)} years ago`;
}

function toTitleCase(s: string) {
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export function EdgeDetailOverlay({ edge, onClose, onDeleteEdge }: Props) {
  const isStale = edge.stale;
  const canDelete = !!edge.id;
  const [showConfirm, setShowConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (!edge.id) return;
    setDeleting(true);
    onDeleteEdge?.(edge.id);
    setShowConfirm(false);
    setDeleting(false);
  };

  return (
    <>
      <div className={`absolute top-4 right-4 w-80 glass border rounded-2xl shadow-2xl z-50 p-5 space-y-5 ${
        isStale ? 'border-[hsl(var(--warning))]/20 shadow-[hsl(var(--warning))]/5' : 'border-border/20 shadow-primary/5'
      }`}>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            {isStale ? (
              <AlertTriangle className="h-4 w-4 text-[hsl(var(--warning))]" />
            ) : (
              <Zap className="h-4 w-4 text-primary" />
            )}
            <h3 className="text-base font-display font-semibold text-foreground">
              {isStale ? 'Stale Relationship' : 'Relationship'}
            </h3>
          </div>
          <button onClick={onClose} className="glass-button p-1.5 rounded-full text-muted-foreground hover:text-foreground transition-colors">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="flex items-center gap-2.5 text-sm">
          <span className="glass-button px-3 py-1.5 text-primary rounded-full">
            {edge.sourceName || edge.source}
          </span>
          <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/40" />
          <span className="glass-button px-3 py-1.5 text-accent-foreground rounded-full">
            {edge.targetName || edge.target}
          </span>
        </div>

        <div className="space-y-1.5">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/50">Type</p>
          <p className="text-base text-primary font-display">{toTitleCase(edge.type)}</p>
        </div>

        <div className="space-y-1.5">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/50">Fact</p>
          <p className="text-sm text-foreground/80 leading-relaxed">{edge.fact}</p>
        </div>

        {/* Temporal info */}
        {(edge.created_at || edge.updated_at) && (
          <div className="pt-4 border-t border-border/15 space-y-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground/50">
              <Clock className="h-3.5 w-3.5" />
              <span className="uppercase tracking-[0.15em]">Timeline</span>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              {edge.created_at && (
                <div>
                  <p className="text-[10px] text-muted-foreground/40 uppercase tracking-wider">Created</p>
                  <p className="text-muted-foreground mt-0.5">{timeAgo(edge.created_at)}</p>
                </div>
              )}
              {edge.updated_at && (
                <div>
                  <p className="text-[10px] text-muted-foreground/40 uppercase tracking-wider">Updated</p>
                  <p className={`mt-0.5 ${isStale ? 'text-[hsl(var(--warning))]' : 'text-muted-foreground'}`}>{timeAgo(edge.updated_at)}</p>
                </div>
              )}
            </div>
            {isStale && (
              <div className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-[hsl(var(--warning))]/8 border border-[hsl(var(--warning))]/15">
                <AlertTriangle className="h-3.5 w-3.5 text-[hsl(var(--warning))] shrink-0" />
                <p className="text-xs text-[hsl(var(--warning))]">This relationship may be outdated or overwritten.</p>
              </div>
            )}
          </div>
        )}

        {/* Delete */}
        <div className="pt-4 border-t border-border/15">
          {canDelete ? (
            <button
              onClick={() => setShowConfirm(true)}
              className="w-full glass-button flex items-center justify-center gap-2 px-4 py-2.5 rounded-full text-destructive text-sm hover:bg-destructive/10 transition-colors"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete Relationship
            </button>
          ) : (
            <div className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-secondary/20 text-xs text-muted-foreground/50">
              <Ban className="h-3 w-3 shrink-0" />
              <span>This relationship cannot be deleted directly.</span>
            </div>
          )}
        </div>
      </div>

      <AlertDialog open={showConfirm} onOpenChange={setShowConfirm}>
        <AlertDialogContent className="glass border-border/20 rounded-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-foreground font-display text-lg">Delete relationship?</AlertDialogTitle>
            <AlertDialogDescription className="text-sm leading-relaxed">
              Remove the "{toTitleCase(edge.type)}" relationship between {edge.sourceName || edge.source} and {edge.targetName || edge.target}.
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
              {deleting ? 'Deleting…' : 'Delete Relationship'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
