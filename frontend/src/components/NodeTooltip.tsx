interface Props {
  name: string;
  summary: string;
  position: { x: number; y: number };
}

export function NodeTooltip({ name, summary, position }: Props) {
  return (
    <div
      className="fixed z-[60] pointer-events-none glass border border-border/30 rounded-lg px-4 py-2.5 shadow-lg shadow-primary/10 max-w-xs"
      style={{ left: position.x + 12, top: position.y - 10 }}
    >
      <p className="text-sm font-medium text-foreground">{name}</p>
      {summary && <p className="text-xs text-muted-foreground mt-1 line-clamp-3 leading-relaxed">{summary}</p>}
    </div>
  );
}
