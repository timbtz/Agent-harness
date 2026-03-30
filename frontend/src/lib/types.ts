export type EpisodeCategory = 'decision' | 'insight' | 'error' | 'goal' | 'architecture';
export type EpisodeStatus = 'pending' | 'processing' | 'complete' | 'failed';

export interface Project {
  project_id: string;
  name: string;
  description: string;
  created_at: string;
  repo_path: string | null;
  episode_count: number;
}

export interface GraphNode {
  id: string;
  name: string;
  summary: string;
  created_at?: string;
  updated_at?: string;
  node_type?: 'entity' | 'episodic';
  category?: EpisodeCategory;
}

export interface GraphEdge {
  id?: string;
  source: string;
  target: string;
  fact: string;
  type: string;
  created_at?: string;
  updated_at?: string;
  valid_at?: string;
  invalid_at?: string;
  stale?: boolean;
  edge_kind?: 'semantic' | 'mentions';
}

export interface ProjectGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface HealthStatus {
  status: string;
  falkordb_connected: boolean;
  projects_count: number;
}

export interface Episode {
  id: string;
  project_id: string;
  category: EpisodeCategory;
  content: string;
  status: EpisodeStatus;
  created_at: string;
}
