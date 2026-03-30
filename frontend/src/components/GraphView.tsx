import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Html } from '@react-three/drei';
import { EffectComposer, Bloom, ChromaticAberration } from '@react-three/postprocessing';
import * as THREE from 'three';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { useQueryClient } from '@tanstack/react-query';
import { useProjects } from '@/hooks/useProjects';
import { useProjectGraph } from '@/hooks/useProjectGraph';
import { useToast } from '@/hooks/use-toast';
import { api } from '@/lib/api';
import { CATEGORY_COLORS } from '@/lib/colors';
import { EdgeDetailOverlay } from './EdgeDetailOverlay';
import { NodeDetailPanel } from './NodeDetailPanel';
import type { Project, GraphEdge } from '@/lib/types';

interface Props {
  selectedProject: Project | null;
  onSelectProject: (project: Project) => void;
  externalNavTarget?: string | null;
  onNavHandled?: () => void;
}

/* ───────── helpers ───────── */
function toTitleCase(s: string) {
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function freshness(updated_at?: string, maxAgeDays = 60): number {
  if (!updated_at) return 0.5;
  const age = (Date.now() - new Date(updated_at).getTime()) / 86400000;
  return Math.max(0, Math.min(1, 1 - age / maxAgeDays));
}

/** Pure white (recent) to deep purple (old) — like stellar temperature */
function freshnessColor(f: number): string {
  const r = Math.round(0x3d + f * (0xff - 0x3d));
  const g = Math.round(0x2a + f * (0xff - 0x2a));
  const b = Math.round(0x6e + f * (0xff - 0x6e));
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

/** Edge color: purple-blue to cream spectrum */
function edgeColor(f: number, stale?: boolean): string {
  if (stale) {
    const r = Math.round(140 + f * 40);
    const g = Math.round(80 + f * 30);
    const b = Math.round(50 + f * 20);
    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
  }
  const r = Math.round(0x30 + f * (0x99 - 0x30));
  const g = Math.round(0x25 + f * (0x88 - 0x25));
  const b = Math.round(0x55 + f * (0xcc - 0x55));
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

function timeAgo(iso?: string): string {
  if (!iso) return '';
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (days === 0) return 'today';
  if (days === 1) return '1d ago';
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

/* ───────── Force simulation ───────── */
function useForceLayout(
  nodes: { id: string; [k: string]: any }[],
  links: { source: string; target: string; [k: string]: any }[]
) {
  return useMemo(() => {
    if (!nodes.length) return { positions: new Map<string, [number, number, number]>() };
    const positions = new Map<string, [number, number, number]>();
    const n = nodes.length;
    nodes.forEach((node, i) => {
      const phi = Math.acos(-1 + (2 * i + 1) / n);
      const theta = Math.sqrt(n * Math.PI) * phi;
      const r = 5 + Math.random() * 3;
      positions.set(node.id, [
        r * Math.cos(theta) * Math.sin(phi),
        r * Math.sin(theta) * Math.sin(phi),
        r * Math.cos(phi),
      ]);
    });
    for (let iter = 0; iter < 80; iter++) {
      const ids = Array.from(positions.keys());
      for (let i = 0; i < ids.length; i++) {
        for (let j = i + 1; j < ids.length; j++) {
          const a = positions.get(ids[i])!;
          const b = positions.get(ids[j])!;
          const dx = a[0] - b[0], dy = a[1] - b[1], dz = a[2] - b[2];
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) || 0.1;
          const force = 2.0 / (dist * dist);
          const fx = (dx / dist) * force, fy = (dy / dist) * force, fz = (dz / dist) * force;
          a[0] += fx; a[1] += fy; a[2] += fz;
          b[0] -= fx; b[1] -= fy; b[2] -= fz;
        }
      }
      links.forEach(l => {
        const a = positions.get(l.source);
        const b = positions.get(l.target);
        if (!a || !b) return;
        const dx = b[0] - a[0], dy = b[1] - a[1], dz = b[2] - a[2];
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) || 0.1;
        const force = (dist - 3) * 0.02;
        const fx = (dx / dist) * force, fy = (dy / dist) * force, fz = (dz / dist) * force;
        a[0] += fx; a[1] += fy; a[2] += fz;
        b[0] -= fx; b[1] -= fy; b[2] -= fz;
      });
    }
    return { positions };
  }, [nodes, links]);
}

/* ───────── Glowing Node ───────── */
function GlowNode({
  position, size, color, emissiveIntensity = 2, opacity = 0.9,
  shape = 'icosahedron',
  onClick, onPointerOver, onPointerOut, label, ageLabel, categoryLabel,
}: {
  position: [number, number, number]; size: number; color: string;
  emissiveIntensity?: number; opacity?: number;
  shape?: 'icosahedron' | 'octahedron';
  onClick?: () => void;
  onPointerOver?: (e: any) => void; onPointerOut?: () => void;
  label?: string; ageLabel?: string; categoryLabel?: string;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  useFrame((_, delta) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += delta * (shape === 'octahedron' ? 0.6 : 0.3);
      const scale = hovered ? 1.3 : 1;
      meshRef.current.scale.lerp(new THREE.Vector3(scale, scale, scale), 0.1);
    }
  });

  return (
    <group position={position}>
      <mesh
        ref={meshRef}
        onClick={(e) => { e.stopPropagation(); onClick?.(); }}
        onPointerOver={(e) => { e.stopPropagation(); setHovered(true); onPointerOver?.(e); document.body.style.cursor = 'pointer'; }}
        onPointerOut={() => { setHovered(false); onPointerOut?.(); document.body.style.cursor = 'default'; }}
      >
        {shape === 'octahedron'
          ? <octahedronGeometry args={[size * 0.9, 0]} />
          : <icosahedronGeometry args={[size, 2]} />
        }
        <meshStandardMaterial
          color={color} emissive={color}
          emissiveIntensity={hovered ? emissiveIntensity * 1.8 : emissiveIntensity}
          transparent opacity={opacity} roughness={0.2} metalness={0.8}
        />
      </mesh>
      <mesh>
        <sphereGeometry args={[size * 1.6, 16, 16]} />
        <meshBasicMaterial color={color} transparent opacity={hovered ? 0.15 : 0.06} />
      </mesh>
      {label && hovered && (
        <Html distanceFactor={15} center style={{ pointerEvents: 'none' }}>
          <div className="px-3 py-1.5 rounded-full glass-button whitespace-nowrap text-sm font-display font-semibold text-foreground shadow-lg shadow-primary/10">
            {categoryLabel && (
              <span className="mr-2 text-[10px] uppercase tracking-widest opacity-70">[{categoryLabel}]</span>
            )}
            <span>{label}</span>
            {ageLabel && (
              <span className="ml-2 text-[10px] text-muted-foreground font-mono">{ageLabel}</span>
            )}
          </div>
        </Html>
      )}
    </group>
  );
}

/* ───────── Directed Edge ───────── */
function DirectedEdge({
  start, end, onClick, edgeType, color = '#997755', stale = false, ageLabel, edgeKind = 'semantic',
}: {
  start: [number, number, number]; end: [number, number, number];
  onClick?: () => void; edgeType: string; color?: string;
  stale?: boolean; ageLabel?: string; edgeKind?: 'semantic' | 'mentions';
}) {
  const isMentions = edgeKind === 'mentions';
  const groupRef = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState(false);
  const particleRefs = useRef<THREE.Mesh[]>([]);

  const startV = useMemo(() => new THREE.Vector3(...start), [start]);
  const endV = useMemo(() => new THREE.Vector3(...end), [end]);
  const dir = useMemo(() => endV.clone().sub(startV), [startV, endV]);
  const len = useMemo(() => dir.length(), [dir]);

  const lineObj = useMemo(() => {
    const g = new THREE.BufferGeometry().setFromPoints([startV, endV]);
    const baseOpacity = isMentions ? 0.08 : (hovered ? 0.7 : 0.3);
    const m = new THREE.LineBasicMaterial({ color, transparent: true, opacity: baseOpacity });
    return new THREE.Line(g, m);
  }, [startV, endV, color, hovered, isMentions]);

  const arrowPos = useMemo(() => startV.clone().add(dir.clone().multiplyScalar(0.85)), [startV, dir]);
  const arrowQuat = useMemo(() => {
    const q = new THREE.Quaternion();
    q.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
    return q;
  }, [dir]);

  useFrame((_, delta) => {
    if (isMentions) return;
    particleRefs.current.forEach((mesh, i) => {
      if (!mesh) return;
      const userData = mesh.userData as { t: number };
      userData.t = (userData.t + delta * 0.15) % 1;
      const offset = (i * 0.5) % 1;
      const t = (userData.t + offset) % 1;
      const pos = startV.clone().lerp(endV, t);
      mesh.position.copy(pos);
    });
  });

  const hitPos = useMemo(() => startV.clone().add(dir.clone().multiplyScalar(0.5)), [startV, dir]);

  if (isMentions) {
    return (
      <group ref={groupRef}>
        <primitive object={lineObj} />
      </group>
    );
  }

  return (
    <group ref={groupRef}>
      <primitive object={lineObj} />

      <mesh position={arrowPos} quaternion={arrowQuat}>
        <coneGeometry args={[0.12, 0.35, 6]} />
        <meshBasicMaterial color={hovered ? '#e8ddd0' : color} transparent opacity={hovered ? 0.8 : 0.5} />
      </mesh>

      {[0, 1].map(i => (
        <mesh key={i} ref={(el) => { if (el) { particleRefs.current[i] = el; el.userData.t = i * 0.5; } }}>
          <sphereGeometry args={[0.04, 8, 8]} />
          <meshBasicMaterial color={stale ? '#aa7744' : '#d8cce8'} transparent opacity={0.7} />
        </mesh>
      ))}

      {hovered && (
        <Html position={hitPos.toArray() as [number, number, number]} center style={{ pointerEvents: 'none' }}>
          <div className={`px-2.5 py-1.5 rounded-md backdrop-blur-sm whitespace-nowrap text-[10px] font-mono shadow-lg ${
            stale
              ? 'bg-card/95 border border-[hsl(var(--warning))]/40 text-[hsl(var(--warning))] shadow-[hsl(var(--warning))]/10'
              : 'bg-card/95 border border-primary/30 text-primary shadow-primary/10'
          }`}>
            <span>{toTitleCase(edgeType)}</span>
            {stale && <span className="ml-1.5 text-[9px] opacity-70">STALE</span>}
            {ageLabel && <span className="ml-1.5 text-[9px] opacity-50">{ageLabel}</span>}
          </div>
        </Html>
      )}

      <mesh position={hitPos} quaternion={arrowQuat}
        onClick={(e) => { e.stopPropagation(); onClick?.(); }}
        onPointerOver={(e) => { e.stopPropagation(); setHovered(true); document.body.style.cursor = 'pointer'; }}
        onPointerOut={() => { setHovered(false); document.body.style.cursor = 'default'; }}
        visible={false}
      >
        <cylinderGeometry args={[0.15, 0.15, len, 4]} />
        <meshBasicMaterial transparent opacity={0} />
      </mesh>
    </group>
  );
}

/* ───────── Graph Scene ───────── */
function GraphScene({
  selectedProject, onSelectProject, projects, graphData,
  onEdgeClick, onNodeClick, flyTargetId,
}: {
  selectedProject: Project | null;
  onSelectProject: (p: Project) => void;
  projects: Project[] | undefined;
  graphData: { nodes: any[]; edges: any[] } | undefined;
  onEdgeClick: (edge: any) => void;
  onNodeClick: (node: any | null) => void;
  flyTargetId: string | null;
}) {
  const controlsRef = useRef<OrbitControlsImpl>(null);
  const [flyTarget, setFlyTarget] = useState<THREE.Vector3 | null>(null);

  const { nodes, links } = useMemo(() => {
    if (selectedProject && graphData) {
      const degreeMap: Record<string, number> = {};
      graphData.edges.forEach(e => {
        degreeMap[e.source] = (degreeMap[e.source] || 0) + 1;
        degreeMap[e.target] = (degreeMap[e.target] || 0) + 1;
      });
      return {
        nodes: graphData.nodes.map(n => ({
          id: n.id, name: n.name, summary: n.summary,
          node_type: n.node_type ?? 'entity',
          category: n.category,
          val: Math.min(0.6, Math.max(0.15, (degreeMap[n.id] || 1) * 0.08)),
          created_at: n.created_at, updated_at: n.updated_at,
          freshness: freshness(n.updated_at ?? n.created_at),
        })),
        links: graphData.edges.map(e => ({
          id: e.id, source: e.source, target: e.target, fact: e.fact, type: e.type,
          created_at: e.created_at, updated_at: e.updated_at,
          invalid_at: e.invalid_at,
          stale: e.stale,
          edge_kind: e.edge_kind ?? 'semantic',
          freshness: freshness(e.updated_at),
        })),
      };
    }
    if (!selectedProject && projects) {
      return {
        nodes: projects.map(p => ({
          id: p.project_id, name: p.name,
          val: Math.min(0.7, Math.max(0.25, p.episode_count * 0.012)),
          project: p, freshness: 1,
        })),
        links: [] as any[],
      };
    }
    return { nodes: [], links: [] };
  }, [selectedProject, projects, graphData]);

  const { positions } = useForceLayout(nodes, links);

  // Trigger fly-to when flyTargetId changes
  useEffect(() => {
    if (!flyTargetId) return;
    const pos = positions.get(flyTargetId);
    if (pos) setFlyTarget(new THREE.Vector3(...pos));
  }, [flyTargetId, positions]);

  // Camera lerp animation
  useFrame(({ camera }) => {
    if (!flyTarget || !controlsRef.current) return;
    const controls = controlsRef.current;
    const dir = camera.position.clone().sub(flyTarget).normalize();
    const targetCamPos = flyTarget.clone().add(dir.multiplyScalar(8));
    camera.position.lerp(targetCamPos, 0.06);
    (controls.target as THREE.Vector3).lerp(flyTarget, 0.06);
    controls.update();
    if (camera.position.distanceTo(targetCamPos) < 0.05) setFlyTarget(null);
  });

  const nodeMap = useMemo(() => {
    const m = new Map<string, { id: string; name: string; summary?: string; updated_at?: string }>();
    nodes.forEach(n => m.set(n.id, n));
    return m;
  }, [nodes]);

  return (
    <>
      <ambientLight intensity={0.06} />
      <pointLight position={[10, 10, 10]} intensity={0.5} color="#9988cc" />
      <pointLight position={[-10, -5, -10]} intensity={0.3} color="#5544aa" />
      <pointLight position={[0, -10, 5]} intensity={0.2} color="#eeddcc" />

      {links.map((link, i) => {
        const startPos = positions.get(link.source);
        const endPos = positions.get(link.target);
        if (!startPos || !endPos) return null;
        return (
          <DirectedEdge
            key={`edge-${i}`}
            start={startPos}
            end={endPos}
            edgeType={link.type}
            color={edgeColor(link.freshness, link.stale)}
            stale={link.stale}
            ageLabel={timeAgo(link.updated_at)}
            edgeKind={link.edge_kind}
            onClick={() => {
              if (link.edge_kind === 'mentions') return;
              const sNode = nodeMap.get(link.source);
              const tNode = nodeMap.get(link.target);
              onEdgeClick({
                id: link.id,
                source: link.source, target: link.target,
                fact: link.fact, type: link.type,
                sourceName: sNode?.name, targetName: tNode?.name,
                created_at: link.created_at, updated_at: link.updated_at,
                stale: link.stale,
              });
            }}
          />
        );
      })}

      {nodes.map(node => {
        const pos = positions.get(node.id);
        if (!pos) return null;
        const isKnowledge = !!selectedProject;
        const isEpisodic = node.node_type === 'episodic';
        const f = node.freshness as number;
        const color = isEpisodic
          ? (CATEGORY_COLORS[node.category as string] ?? '#888888')
          : isKnowledge ? freshnessColor(f) : '#c8b8e0';
        const emissive = isEpisodic ? 1.2 : isKnowledge ? (1 + f * 2) : 2;
        const opacity = isEpisodic ? 0.75 : isKnowledge ? (0.4 + f * 0.55) : 0.9;
        const hoverLabel = isEpisodic
          ? (node.summary ? node.summary.slice(0, 35) + (node.summary.length > 35 ? '…' : '') : '')
          : node.name;
        return (
          <GlowNode
            key={node.id}
            position={pos}
            size={isEpisodic ? Math.max(node.val * 0.7, 0.12) : node.val}
            color={color}
            emissiveIntensity={emissive}
            opacity={opacity}
            shape={isEpisodic ? 'octahedron' : 'icosahedron'}
            label={hoverLabel}
            ageLabel={isKnowledge ? timeAgo(node.updated_at ?? node.created_at) : undefined}
            categoryLabel={isEpisodic ? node.category : undefined}
            onClick={() => {
              if (!selectedProject && node.project) {
                onSelectProject(node.project);
              } else if (selectedProject) {
                onNodeClick(node);
                setFlyTarget(new THREE.Vector3(...pos));
              }
            }}
          />
        );
      })}

      <EffectComposer>
        <Bloom luminanceThreshold={0.2} luminanceSmoothing={0.9} intensity={1.5} mipmapBlur />
        <ChromaticAberration
          offset={new THREE.Vector2(0.0005, 0.0005)}
          radialModulation={false} modulationOffset={0}
        />
      </EffectComposer>

      <OrbitControls ref={controlsRef} enablePan={false} enableZoom autoRotate autoRotateSpeed={0.4} minDistance={5} maxDistance={40} />
    </>
  );
}

/* ───────── Temporal Scrubber ───────── */
function TemporalScrubber({
  nodes, edges, scrubTime, onScrub,
}: {
  nodes: any[];
  edges: any[];
  scrubTime: Date | null;
  onScrub: (d: Date | null) => void;
}) {
  const { minMs, maxMs } = useMemo(() => {
    const timestamps: number[] = [];
    nodes.forEach(n => { if (n.created_at) timestamps.push(new Date(n.created_at).getTime()); });
    edges.forEach(e => {
      if (e.created_at) timestamps.push(new Date(e.created_at).getTime());
      if (e.valid_at) timestamps.push(new Date(e.valid_at).getTime());
    });
    if (!timestamps.length) return { minMs: Date.now() - 86400000 * 30, maxMs: Date.now() };
    return { minMs: Math.min(...timestamps), maxMs: Date.now() };
  }, [nodes, edges]);

  const rangeMs = maxMs - minMs || 1;
  const sliderVal = scrubTime ? Math.round(((scrubTime.getTime() - minMs) / rangeMs) * 1000) : 1000;
  const isLive = !scrubTime;

  const handleChange = (v: number) => {
    if (v >= 1000) { onScrub(null); return; }
    onScrub(new Date(minMs + (v / 1000) * rangeMs));
  };

  const displayDate = scrubTime
    ? scrubTime.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    : 'Live';

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-3 px-5 py-3 bg-card/70 backdrop-blur-xl border border-border/50 rounded-xl text-[11px] font-mono text-muted-foreground shadow-lg min-w-[340px]">
      <span className="text-[9px] uppercase tracking-[0.15em] shrink-0">Time</span>
      <input
        type="range"
        min={0}
        max={1000}
        value={sliderVal}
        onChange={e => handleChange(Number(e.target.value))}
        className="flex-1 h-1.5 accent-primary cursor-pointer"
      />
      <span className={`w-24 text-right shrink-0 ${isLive ? 'text-primary' : ''}`}>
        {isLive ? '● Live' : displayDate}
      </span>
      {!isLive && (
        <button
          onClick={() => onScrub(null)}
          className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
          title="Reset to live view"
        >
          ×
        </button>
      )}
    </div>
  );
}

/* ───────── Exported component ───────── */
export function GraphView({ selectedProject, onSelectProject, externalNavTarget, onNavHandled }: Props) {
  const { data: projects, isLoading: loadingProjects } = useProjects();
  const { data: rawGraphData, isLoading: loadingGraph } = useProjectGraph(selectedProject?.project_id ?? null);
  const [selectedEdge, setSelectedEdge] = useState<(GraphEdge & { sourceName?: string; targetName?: string }) | null>(null);
  const [selectedNode, setSelectedNode] = useState<{ id: string; name: string; summary?: string; updated_at?: string; node_type?: string; category?: string } | null>(null);
  const [scrubTime, setScrubTime] = useState<Date | null>(null);
  const [flyTargetId, setFlyTargetId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // Handle external navigation (from EpisodeList / SearchPanel / TimelinePanel)
  useEffect(() => {
    if (!externalNavTarget || !rawGraphData) return;
    const node = rawGraphData.nodes.find(n => n.id === externalNavTarget);
    if (node) {
      setSelectedNode(node);
      setSelectedEdge(null);
      setFlyTargetId(externalNavTarget);
    }
    onNavHandled?.();
  }, [externalNavTarget, rawGraphData, onNavHandled]);

  // Reset scrubber when project changes
  useEffect(() => {
    setScrubTime(null);
  }, [selectedProject?.project_id]);

  // Filter graph data by scrub time
  const graphData = useMemo(() => {
    if (!rawGraphData) return rawGraphData;
    if (!scrubTime) {
      return {
        nodes: rawGraphData.nodes,
        edges: rawGraphData.edges.filter((e: any) => !e.invalid_at),
      };
    }
    const t = scrubTime;
    return {
      nodes: rawGraphData.nodes.filter((n: any) => !n.created_at || new Date(n.created_at) <= t),
      edges: rawGraphData.edges.filter((e: any) => {
        const createdBefore = !e.created_at || new Date(e.created_at) <= t;
        const notYetInvalid = !e.invalid_at || new Date(e.invalid_at) > t;
        return createdBefore && notYetInvalid;
      }),
    };
  }, [rawGraphData, scrubTime]);

  const isLoading = selectedProject ? loadingGraph : loadingProjects;

  const refetchGraph = useCallback(() => {
    if (selectedProject) {
      queryClient.invalidateQueries({ queryKey: ['projectGraph', selectedProject.project_id] });
    }
  }, [selectedProject, queryClient]);

  const handleDeleteNode = useCallback(async (nodeId: string) => {
    if (!selectedProject) return;
    try {
      await api.deleteGraphNode(selectedProject.project_id, nodeId);
      setSelectedNode(null);
      refetchGraph();
      toast({ title: 'Node deleted', description: `Successfully removed node and its edges.` });
    } catch (err) {
      toast({ title: 'Delete failed', description: String(err), variant: 'destructive' });
    }
  }, [selectedProject, refetchGraph, toast]);

  const handleDeleteEdge = useCallback(async (edgeId: string) => {
    if (!selectedProject) return;
    try {
      await api.deleteGraphEdge(selectedProject.project_id, edgeId);
      setSelectedEdge(null);
      refetchGraph();
      toast({ title: 'Relationship deleted', description: `Successfully removed the relationship.` });
    } catch (err) {
      toast({ title: 'Delete failed', description: String(err), variant: 'destructive' });
    }
  }, [selectedProject, refetchGraph, toast]);

  const connectedEdges = useMemo(() => {
    if (!selectedNode || !rawGraphData) return [];
    const nodeNameMap = new Map(rawGraphData.nodes.map((n: any) => [n.id, n.name]));
    return rawGraphData.edges
      .filter((e: any) => e.source === selectedNode.id || e.target === selectedNode.id)
      .map((e: any) => ({
        ...e,
        sourceName: nodeNameMap.get(e.source) || e.source,
        targetName: nodeNameMap.get(e.target) || e.target,
        direction: e.source === selectedNode.id ? 'outgoing' as const : 'incoming' as const,
      }));
  }, [selectedNode, rawGraphData]);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-background">
        <div className="text-center space-y-3">
          <div className="relative mx-auto h-32 w-32">
            <div className="absolute inset-0 rounded-full border border-primary/30 animate-ping" />
            <div className="absolute inset-4 rounded-full border border-primary/50 animate-pulse" />
            <div className="absolute inset-8 rounded-full bg-primary/10 animate-pulse" />
          </div>
          <p className="text-sm text-muted-foreground animate-pulse font-display italic">Initializing graph…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 relative bg-background overflow-hidden">
      {/* Subtle warm grid overlay */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.02]"
        style={{
          backgroundImage: 'linear-gradient(hsl(var(--primary) / 0.3) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--primary) / 0.3) 1px, transparent 1px)',
          backgroundSize: '60px 60px',
        }}
      />

      <Canvas
        camera={{ position: [0, 0, 18], fov: 60 }}
        gl={{ antialias: true, alpha: true }}
        style={{ background: 'transparent' }}
      >
        <GraphScene
          selectedProject={selectedProject}
          onSelectProject={onSelectProject}
          projects={projects}
          graphData={graphData}
          onEdgeClick={(edge) => { setSelectedNode(null); setSelectedEdge(edge); }}
          onNodeClick={(node) => { setSelectedEdge(null); setSelectedNode(node); }}
          flyTargetId={flyTargetId}
        />
      </Canvas>

      {selectedEdge && (
        <EdgeDetailOverlay
          edge={selectedEdge}
          onClose={() => setSelectedEdge(null)}
          onDeleteEdge={handleDeleteEdge}
        />
      )}

      {selectedNode && (
        <NodeDetailPanel
          node={selectedNode}
          edges={connectedEdges}
          onClose={() => setSelectedNode(null)}
          onDeleteNode={handleDeleteNode}
          onNavigateToNode={(nodeId) => {
            const node = rawGraphData?.nodes.find((n: any) => n.id === nodeId);
            if (node) {
              setSelectedNode(node);
              setFlyTargetId(nodeId);
              setSelectedEdge(null);
            }
          }}
        />
      )}

      {/* Mode indicator */}
      <div className="absolute top-4 left-4 px-4 py-2 bg-card/60 backdrop-blur-xl border border-border/50 rounded-lg text-xs text-muted-foreground font-mono flex items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
        {selectedProject ? `GRAPH: ${selectedProject.name}` : 'NEURAL OVERVIEW'}
      </div>

      {/* Legend */}
      {selectedProject && (
        <div className="absolute bottom-20 left-4 px-4 py-3 bg-card/70 backdrop-blur-xl border border-border/50 rounded-lg text-[10px] text-muted-foreground font-mono space-y-1.5">
          <p className="text-[9px] uppercase tracking-[0.15em] mb-2 text-foreground/60">Temporal</p>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-white shadow-sm shadow-white/60" />
            <span>Recent entity</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-[#3d2a6e]" />
            <span>Older entity</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-[#aa7744]" />
            <span>Stale / overwritten</span>
          </div>
          <p className="text-[9px] uppercase tracking-[0.15em] mt-3 mb-2 text-foreground/60">Episodes ◆</p>
          {Object.entries(CATEGORY_COLORS).map(([cat, col]) => (
            <div key={cat} className="flex items-center gap-2">
              <div className="w-3 h-3 rotate-45 border border-current" style={{ background: col, boxShadow: `0 0 4px ${col}` }} />
              <span>{cat}</span>
            </div>
          ))}
        </div>
      )}

      {/* Temporal scrubber */}
      {selectedProject && rawGraphData && (
        <TemporalScrubber
          nodes={rawGraphData.nodes}
          edges={rawGraphData.edges}
          scrubTime={scrubTime}
          onScrub={setScrubTime}
        />
      )}
    </div>
  );
}
