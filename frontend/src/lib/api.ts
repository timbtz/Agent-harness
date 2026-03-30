import type { Project, ProjectGraph, HealthStatus, Episode } from './types';
import { mockHealth, mockProjects, mockGraphs, mockEpisodes, mockInsights, mockSearch } from './mockData';

const BASE_URL = '/api';
const USE_MOCK = true; // Fallback to mock data when API unavailable

async function fetchApi<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

async function withMock<T>(apiFn: () => Promise<T>, mockFn: () => T): Promise<T> {
  try {
    return await apiFn();
  } catch {
    if (USE_MOCK) return mockFn();
    throw new Error('API unavailable');
  }
}

/** Backend episodes use episode_id; normalize to id for the frontend. */
function normalizeEpisode(ep: any): Episode {
  return {
    id: ep.episode_id ?? ep.id,
    project_id: ep.project_id,
    category: ep.category,
    content: ep.content,
    status: ep.status,
    created_at: ep.created_at,
  };
}

export const api = {
  getHealth: () =>
    withMock(() => fetchApi<HealthStatus>('/health'), () => mockHealth),

  getProjects: () =>
    withMock(() => fetchApi<Project[]>('/projects'), () => mockProjects),

  getProject: (id: string) =>
    withMock(() => fetchApi<Project>(`/projects/${id}`), () => mockProjects.find(p => p.project_id === id)!),

  getProjectGraph: (id: string) =>
    withMock(
      () => fetchApi<ProjectGraph>(`/projects/${id}/graph`),
      () => mockGraphs[id] || { nodes: [], edges: [] }
    ),

  getProjectInsights: async (id: string, page = 1, limit = 20, category?: string) => {
    const params = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (category && category !== 'all') params.set('category', category);
    return withMock(
      async () => {
        // Backend returns {items, total, page, limit} — normalize to {episodes, total}
        const data = await fetchApi<{ items: any[]; total: number }>(`/projects/${id}/insights?${params}`);
        return { episodes: data.items.map(normalizeEpisode), total: data.total };
      },
      () => mockInsights(id, category)
    );
  },

  getProjectTimeline: (id: string) =>
    withMock(
      async () => {
        const data = await fetchApi<any[]>(`/projects/${id}/timeline`);
        return data.map(normalizeEpisode);
      },
      () => [...(mockEpisodes[id] || [])].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
    ),

  searchProject: (id: string, query: string, limit = 10) =>
    withMock(
      async () => {
        // Backend returns {query, results: SearchResult[], total} — map to Episode shape for UI
        const data = await fetchApi<{ results: any[]; total: number }>(`/projects/${id}/search`, {
          method: 'POST',
          body: JSON.stringify({ query, limit }),
        });
        return data.results.map((r, i): Episode => ({
          id: r.entity_name || `sr-${i}`,
          project_id: id,
          category: 'insight',
          content: r.content,
          status: 'complete',
          created_at: r.created_at ?? new Date().toISOString(),
        }));
      },
      () => mockSearch(id, query)
    ),

  deleteProject: (id: string) => fetchApi<void>(`/projects/${id}`, { method: 'DELETE' }),
  deleteEpisode: (projectId: string, episodeId: string) =>
    fetchApi<void>(`/projects/${projectId}/episodes/${episodeId}`, { method: 'DELETE' }),

  deleteGraphNode: (projectId: string, nodeId: string) =>
    withMock(
      () => fetchApi<{ deleted: boolean; node_id: string }>(`/projects/${projectId}/graph/nodes/${nodeId}`, { method: 'DELETE' }),
      () => {
        const graph = mockGraphs[projectId];
        if (graph) {
          graph.nodes = graph.nodes.filter(n => n.id !== nodeId);
          graph.edges = graph.edges.filter(e => e.source !== nodeId && e.target !== nodeId);
        }
        return { deleted: true, node_id: nodeId };
      }
    ),

  deleteGraphEdge: (projectId: string, edgeId: string) =>
    withMock(
      () => fetchApi<{ deleted: boolean; edge_id: string }>(`/projects/${projectId}/graph/edges/${edgeId}`, { method: 'DELETE' }),
      () => {
        const graph = mockGraphs[projectId];
        if (graph) {
          graph.edges = graph.edges.filter(e => e.id !== edgeId);
        }
        return { deleted: true, edge_id: edgeId };
      }
    ),
};
