import type { Project, ProjectGraph, Episode, HealthStatus } from './types';

export const mockHealth: HealthStatus = {
  status: 'ok',
  falkordb_connected: true,
  projects_count: 5,
};

export const mockProjects: Project[] = [
  {
    project_id: 'agent-harness',
    name: 'Agent Harness',
    description: 'MCP graph database frontend for interactive agent knowledge graphs',
    created_at: '2025-12-15T10:30:00Z',
    repo_path: '/repos/agent-harness',
    episode_count: 42,
  },
  {
    project_id: 'data-pipeline',
    name: 'Data Pipeline Engine',
    description: 'ETL framework with streaming support and fault-tolerant processing',
    created_at: '2025-11-20T08:00:00Z',
    repo_path: '/repos/data-pipeline',
    episode_count: 28,
  },
  {
    project_id: 'auth-service',
    name: 'Auth Microservice',
    description: 'OAuth2/OIDC identity provider with RBAC and multi-tenant support',
    created_at: '2026-01-05T14:15:00Z',
    repo_path: '/repos/auth-service',
    episode_count: 63,
  },
  {
    project_id: 'ml-orchestrator',
    name: 'ML Orchestrator',
    description: 'Machine learning model training and deployment orchestration platform',
    created_at: '2026-02-10T09:45:00Z',
    repo_path: null,
    episode_count: 17,
  },
  {
    project_id: 'api-gateway',
    name: 'API Gateway',
    description: 'High-performance API gateway with rate limiting, caching, and observability',
    created_at: '2026-03-01T11:00:00Z',
    repo_path: '/repos/api-gateway',
    episode_count: 35,
  },
];

// Helper: generate ISO dates spread across a time range
function daysAgo(d: number) {
  return new Date(Date.now() - d * 86400000).toISOString();
}

export const mockGraphs: Record<string, ProjectGraph> = {
  'agent-harness': {
    nodes: [
      { id: 'n1', name: 'GraphView', summary: 'Main 3D force-graph visualization component handling both project overview and knowledge graph modes', created_at: daysAgo(45), updated_at: daysAgo(1) },
      { id: 'n2', name: 'LeftPanel', summary: 'Sidebar component with project list, episode browser, search, and timeline tabs', created_at: daysAgo(44), updated_at: daysAgo(3) },
      { id: 'n3', name: 'FalkorDB', summary: 'Graph database backend storing entity relationships and project knowledge', created_at: daysAgo(50), updated_at: daysAgo(30) },
      { id: 'n4', name: 'React Query', summary: 'Data fetching layer with caching, polling, and optimistic updates', created_at: daysAgo(42), updated_at: daysAgo(10) },
      { id: 'n5', name: 'MCP Protocol', summary: 'Model Context Protocol for agent-to-graph communication', created_at: daysAgo(40), updated_at: daysAgo(5) },
      { id: 'n6', name: 'Episode Store', summary: 'Persistent storage for decisions, insights, errors, and architecture notes', created_at: daysAgo(48), updated_at: daysAgo(2) },
      { id: 'n7', name: 'ForceGraph3D', summary: 'Three.js-based 3D force-directed graph renderer', created_at: daysAgo(43), updated_at: daysAgo(40) },
      { id: 'n8', name: 'Auth Module', summary: 'Session management and API key validation', created_at: daysAgo(35), updated_at: daysAgo(20) },
      { id: 'n9', name: 'Search Engine', summary: 'Full-text search over episodes with semantic ranking', created_at: daysAgo(30), updated_at: daysAgo(8) },
      { id: 'n10', name: 'WebSocket Hub', summary: 'Real-time graph update notifications via WebSocket', created_at: daysAgo(25), updated_at: daysAgo(4) },
    ],
    edges: [
      { id: 'e-ah-01', source: 'n1', target: 'n7', fact: 'GraphView renders using ForceGraph3D as the underlying 3D engine', type: 'renders_with', created_at: daysAgo(43), updated_at: daysAgo(40), stale: true },
      { id: 'e-ah-02', source: 'n1', target: 'n4', fact: 'GraphView fetches graph data through React Query hooks', type: 'fetches_via', created_at: daysAgo(42), updated_at: daysAgo(2) },
      { id: 'e-ah-03', source: 'n2', target: 'n4', fact: 'LeftPanel uses React Query for project and episode data', type: 'fetches_via', created_at: daysAgo(42), updated_at: daysAgo(3) },
      { id: 'e-ah-04', source: 'n4', target: 'n3', fact: 'React Query calls FalkorDB REST API for graph operations', type: 'queries', created_at: daysAgo(42), updated_at: daysAgo(10) },
      { id: 'e-ah-05', source: 'n5', target: 'n3', fact: 'MCP Protocol bridges agent sessions to FalkorDB graph storage', type: 'bridges', created_at: daysAgo(40), updated_at: daysAgo(5) },
      { id: 'e-ah-06', source: 'n6', target: 'n3', fact: 'Episode Store persists episodes as nodes in FalkorDB', type: 'persists_to', created_at: daysAgo(48), updated_at: daysAgo(30) },
      { id: 'e-ah-07', source: 'n2', target: 'n9', fact: 'LeftPanel search tab triggers full-text search queries', type: 'searches_via', created_at: daysAgo(30), updated_at: daysAgo(8) },
      { id: 'e-ah-08', source: 'n9', target: 'n6', fact: 'Search Engine indexes and queries the Episode Store', type: 'indexes', created_at: daysAgo(30), updated_at: daysAgo(8) },
      { id: 'e-ah-09', source: 'n8', target: 'n4', fact: 'Auth Module provides API tokens used by React Query requests', type: 'authenticates', created_at: daysAgo(35), updated_at: daysAgo(20) },
      { id: 'e-ah-10', source: 'n10', target: 'n1', fact: 'WebSocket Hub pushes real-time graph changes to GraphView', type: 'notifies', created_at: daysAgo(25), updated_at: daysAgo(1) },
      { id: 'e-ah-11', source: 'n10', target: 'n3', fact: 'WebSocket Hub listens to FalkorDB change streams', type: 'subscribes_to', created_at: daysAgo(25), updated_at: daysAgo(4) },
      { id: 'e-ah-12', source: 'n5', target: 'n6', fact: 'MCP Protocol writes agent decisions and insights to Episode Store', type: 'writes_to', created_at: daysAgo(40), updated_at: daysAgo(2) },
    ],
  },
  'data-pipeline': {
    nodes: [
      { id: 'd1', name: 'Ingestion Layer', summary: 'Accepts data from Kafka, S3, HTTP webhooks, and file drops', created_at: daysAgo(60), updated_at: daysAgo(5) },
      { id: 'd2', name: 'Transform Engine', summary: 'Applies user-defined transformations with SQL and Python UDFs', created_at: daysAgo(58), updated_at: daysAgo(3) },
      { id: 'd3', name: 'Schema Registry', summary: 'Manages Avro/Protobuf schemas with compatibility validation', created_at: daysAgo(55), updated_at: daysAgo(15) },
      { id: 'd4', name: 'Sink Connector', summary: 'Writes processed data to Postgres, BigQuery, and Elasticsearch', created_at: daysAgo(50), updated_at: daysAgo(7) },
      { id: 'd5', name: 'Scheduler', summary: 'Cron-based and event-driven pipeline execution orchestrator', created_at: daysAgo(45), updated_at: daysAgo(25) },
      { id: 'd6', name: 'Monitoring', summary: 'Pipeline health metrics, alerting, and dead-letter queue tracking', created_at: daysAgo(40), updated_at: daysAgo(2) },
    ],
    edges: [
      { id: 'e-dp-01', source: 'd1', target: 'd3', fact: 'Ingestion validates incoming data against Schema Registry schemas', type: 'validates_with', created_at: daysAgo(55), updated_at: daysAgo(15) },
      { id: 'e-dp-02', source: 'd1', target: 'd2', fact: 'Raw ingested data flows into the Transform Engine', type: 'feeds', created_at: daysAgo(58), updated_at: daysAgo(3) },
      { id: 'e-dp-03', source: 'd2', target: 'd4', fact: 'Transformed records are sent to configured Sink Connectors', type: 'outputs_to', created_at: daysAgo(50), updated_at: daysAgo(7) },
      { id: 'e-dp-04', source: 'd5', target: 'd1', fact: 'Scheduler triggers pipeline runs on configured intervals', type: 'triggers', created_at: daysAgo(45), updated_at: daysAgo(25), stale: true },
      { id: 'e-dp-05', source: 'd6', target: 'd2', fact: 'Monitoring tracks transform latency and error rates', type: 'observes', created_at: daysAgo(40), updated_at: daysAgo(2) },
      { id: 'e-dp-06', source: 'd6', target: 'd4', fact: 'Monitoring alerts on sink write failures and backpressure', type: 'alerts_on', created_at: daysAgo(40), updated_at: daysAgo(2) },
    ],
  },
  'auth-service': {
    nodes: [
      { id: 'a1', name: 'Token Issuer', summary: 'Generates JWT access and refresh tokens with configurable claims', created_at: daysAgo(90), updated_at: daysAgo(10) },
      { id: 'a2', name: 'OIDC Provider', summary: 'OpenID Connect identity provider with discovery endpoint', created_at: daysAgo(88), updated_at: daysAgo(12) },
      { id: 'a3', name: 'RBAC Engine', summary: 'Role-based access control with hierarchical permission model', created_at: daysAgo(85), updated_at: daysAgo(5) },
      { id: 'a4', name: 'User Store', summary: 'PostgreSQL-backed user and credential storage with argon2 hashing', created_at: daysAgo(90), updated_at: daysAgo(60) },
      { id: 'a5', name: 'Session Manager', summary: 'Redis-backed session lifecycle with sliding expiration', created_at: daysAgo(80), updated_at: daysAgo(3) },
      { id: 'a6', name: 'Audit Logger', summary: 'Immutable audit trail for all authentication and authorization events', created_at: daysAgo(75), updated_at: daysAgo(1) },
      { id: 'a7', name: 'OAuth Clients', summary: 'Client application registry with secret rotation support', created_at: daysAgo(70), updated_at: daysAgo(8) },
    ],
    edges: [
      { id: 'e-as-01', source: 'a2', target: 'a1', fact: 'OIDC Provider delegates token creation to Token Issuer', type: 'delegates_to', created_at: daysAgo(88), updated_at: daysAgo(10) },
      { id: 'e-as-02', source: 'a1', target: 'a4', fact: 'Token Issuer looks up user claims from User Store', type: 'reads_from', created_at: daysAgo(88), updated_at: daysAgo(60), stale: true },
      { id: 'e-as-03', source: 'a3', target: 'a4', fact: 'RBAC Engine loads role assignments from User Store', type: 'queries', created_at: daysAgo(85), updated_at: daysAgo(5) },
      { id: 'e-as-04', source: 'a5', target: 'a1', fact: 'Session Manager validates tokens on each request', type: 'validates_via', created_at: daysAgo(80), updated_at: daysAgo(3) },
      { id: 'e-as-05', source: 'a6', target: 'a5', fact: 'Audit Logger records all session creation and destruction events', type: 'logs', created_at: daysAgo(75), updated_at: daysAgo(1) },
      { id: 'e-as-06', source: 'a7', target: 'a2', fact: 'OAuth Clients authenticate through the OIDC Provider', type: 'authenticates_via', created_at: daysAgo(70), updated_at: daysAgo(8) },
      { id: 'e-as-07', source: 'a6', target: 'a3', fact: 'Audit Logger tracks permission checks and role changes', type: 'logs', created_at: daysAgo(75), updated_at: daysAgo(1) },
    ],
  },
  'ml-orchestrator': {
    nodes: [
      { id: 'm1', name: 'Experiment Tracker', summary: 'Logs hyperparameters, metrics, and artifacts for each training run', created_at: daysAgo(30), updated_at: daysAgo(2) },
      { id: 'm2', name: 'GPU Scheduler', summary: 'Allocates GPU resources across training jobs with priority queues', created_at: daysAgo(28), updated_at: daysAgo(1) },
      { id: 'm3', name: 'Model Registry', summary: 'Versioned model storage with promotion stages (dev/staging/prod)', created_at: daysAgo(25), updated_at: daysAgo(4) },
      { id: 'm4', name: 'Serving Runtime', summary: 'Low-latency model inference with auto-scaling and A/B testing', created_at: daysAgo(20), updated_at: daysAgo(6) },
      { id: 'm5', name: 'Feature Store', summary: 'Centralized feature computation and serving for training and inference', created_at: daysAgo(22), updated_at: daysAgo(3) },
    ],
    edges: [
      { id: 'e-ml-01', source: 'm1', target: 'm3', fact: 'Experiment Tracker promotes best models to Model Registry', type: 'promotes_to', created_at: daysAgo(25), updated_at: daysAgo(2) },
      { id: 'e-ml-02', source: 'm2', target: 'm1', fact: 'GPU Scheduler runs training jobs tracked by Experiment Tracker', type: 'executes_for', created_at: daysAgo(28), updated_at: daysAgo(1) },
      { id: 'e-ml-03', source: 'm3', target: 'm4', fact: 'Model Registry deploys approved models to Serving Runtime', type: 'deploys_to', created_at: daysAgo(20), updated_at: daysAgo(4) },
      { id: 'e-ml-04', source: 'm5', target: 'm2', fact: 'Feature Store provides training features to GPU Scheduler jobs', type: 'provides_features', created_at: daysAgo(22), updated_at: daysAgo(3) },
      { id: 'e-ml-05', source: 'm5', target: 'm4', fact: 'Feature Store serves real-time features for inference requests', type: 'serves', created_at: daysAgo(20), updated_at: daysAgo(3) },
    ],
  },
  'api-gateway': {
    nodes: [
      { id: 'g1', name: 'Router', summary: 'Path-based request routing with regex patterns and header matching', created_at: daysAgo(70), updated_at: daysAgo(2) },
      { id: 'g2', name: 'Rate Limiter', summary: 'Token bucket rate limiting with per-client and global thresholds', created_at: daysAgo(65), updated_at: daysAgo(5) },
      { id: 'g3', name: 'Cache Layer', summary: 'Response caching with TTL, cache invalidation, and stale-while-revalidate', created_at: daysAgo(60), updated_at: daysAgo(10) },
      { id: 'g4', name: 'Auth Middleware', summary: 'JWT validation and API key verification middleware', created_at: daysAgo(68), updated_at: daysAgo(15) },
      { id: 'g5', name: 'Load Balancer', summary: 'Weighted round-robin and least-connections backend selection', created_at: daysAgo(55), updated_at: daysAgo(20) },
      { id: 'g6', name: 'Metrics Collector', summary: 'Prometheus metrics for latency, throughput, and error rates', created_at: daysAgo(50), updated_at: daysAgo(1) },
      { id: 'g7', name: 'Circuit Breaker', summary: 'Prevents cascade failures with configurable failure thresholds', created_at: daysAgo(45), updated_at: daysAgo(35) },
    ],
    edges: [
      { id: 'e-gw-01', source: 'g1', target: 'g4', fact: 'Router passes requests through Auth Middleware before forwarding', type: 'chains', created_at: daysAgo(68), updated_at: daysAgo(2) },
      { id: 'e-gw-02', source: 'g4', target: 'g2', fact: 'Authenticated requests are checked against Rate Limiter quotas', type: 'enforces', created_at: daysAgo(65), updated_at: daysAgo(5) },
      { id: 'e-gw-03', source: 'g2', target: 'g3', fact: 'Rate-limited requests check Cache Layer before hitting backends', type: 'checks', created_at: daysAgo(60), updated_at: daysAgo(10) },
      { id: 'e-gw-04', source: 'g3', target: 'g5', fact: 'Cache misses are forwarded to Load Balancer for backend routing', type: 'forwards_to', created_at: daysAgo(55), updated_at: daysAgo(20) },
      { id: 'e-gw-05', source: 'g5', target: 'g7', fact: 'Load Balancer uses Circuit Breaker to skip unhealthy backends', type: 'protects_with', created_at: daysAgo(45), updated_at: daysAgo(35), stale: true },
      { id: 'e-gw-06', source: 'g6', target: 'g1', fact: 'Metrics Collector instruments all requests entering the Router', type: 'instruments', created_at: daysAgo(50), updated_at: daysAgo(1) },
      { id: 'e-gw-07', source: 'g6', target: 'g7', fact: 'Metrics Collector tracks circuit breaker state transitions', type: 'monitors', created_at: daysAgo(45), updated_at: daysAgo(35), stale: true },
    ],
  },
};

const makeEpisodes = (projectId: string): Episode[] => {
  const categories = ['decision', 'insight', 'error', 'goal', 'architecture'] as const;
  const contents: Record<string, string[]> = {
    'agent-harness': [
      'Decided to use ForceGraph3D for both project overview and knowledge graph visualization modes',
      'FalkorDB Cypher queries for multi-hop traversals are 3x faster than equivalent Neo4j queries for our dataset size',
      'WebSocket connection drops when graph has >500 nodes due to message size limits — need chunked updates',
      'Achieve sub-100ms graph render time for knowledge graphs with up to 200 nodes',
      'Split GraphView into two sub-components: ProjectsOverview and KnowledgeGraph for cleaner separation',
      'React Query stale-while-revalidate pattern provides excellent UX for graph data that changes infrequently',
      'MCP protocol handshake fails silently when agent session token expires — added explicit error handling',
      'Implement real-time collaborative graph editing with conflict resolution via CRDTs',
      'Episode categorization using LLM classification achieves 94% accuracy on our test set',
      'Migrated from REST polling to WebSocket for graph updates — reduced bandwidth by 80%',
    ],
    'data-pipeline': [
      'Chose Apache Arrow as the in-memory format for zero-copy data exchange between transforms',
      'Backpressure handling with bounded queues prevents OOM when sink is slower than source',
      'Schema evolution breaks when removing required fields — added compatibility check in CI',
      'Support exactly-once semantics for Kafka-to-Postgres pipelines',
      'Redesigned transform DAG executor to support parallel branches with join semantics',
      'Dead-letter queue analysis revealed 73% of failures are schema validation errors',
      'Sink connector timeout of 30s is too aggressive for BigQuery bulk loads — increased to 120s',
      'Add support for streaming SQL with tumbling and sliding window aggregations',
    ],
    'auth-service': [
      'Switched from HS256 to RS256 for JWT signing to support key rotation without downtime',
      'Argon2id with memory=64MB provides best security/performance tradeoff for our traffic patterns',
      'Token refresh race condition when multiple tabs send refresh requests simultaneously',
      'Implement passwordless authentication via magic links and WebAuthn/FIDO2',
      'Separated RBAC permission checks into a dedicated microservice for reuse across platform',
      'Redis session store handles 50K concurrent sessions with p99 latency under 2ms',
      'OIDC discovery endpoint returns wrong issuer URL behind reverse proxy — fixed with X-Forwarded headers',
      'Achieve SOC2 Type II compliance for all authentication flows',
      'Multi-tenant isolation uses row-level security in PostgreSQL — zero cross-tenant data leaks in pen test',
      'Added PKCE flow for public OAuth clients to prevent authorization code interception',
      'Audit log ingestion pipeline processes 10K events/sec with sub-second search latency',
      'Client secret rotation grace period of 24h allows zero-downtime rotation',
    ],
    'ml-orchestrator': [
      'Decided to use Ray for distributed training instead of Horovod for better fault tolerance',
      'Model quantization from FP32 to INT8 reduces serving latency by 60% with <1% accuracy loss',
      'GPU OOM errors on A100 when batch size exceeds 256 for our transformer architecture',
      'Achieve model deployment from registry to production in under 5 minutes',
      'Feature Store uses dual-write to both offline (Parquet) and online (Redis) stores',
    ],
    'api-gateway': [
      'Implemented consistent hashing for cache distribution across gateway instances',
      'Token bucket rate limiter with Redis backend handles 100K requests/sec with <1ms overhead',
      'Circuit breaker false-positives during backend deployments — added deployment-aware health checks',
      'Reduce p99 latency to under 10ms for cached responses at 50K RPS',
      'Added gRPC-to-REST transcoding layer for legacy client compatibility',
      'Prometheus histogram buckets redesigned to capture tail latency more accurately',
      'Load balancer weighted routing enables gradual traffic shifting for canary deployments',
      'Cache stampede prevention using probabilistic early recomputation (XFetch algorithm)',
      'Rate limiter now supports sliding window counters for more accurate burst detection',
    ],
  };

  const projectContents = contents[projectId] || contents['agent-harness']!;
  return projectContents.map((content, i) => ({
    id: `${projectId}-ep-${i + 1}`,
    project_id: projectId,
    category: categories[i % categories.length],
    content,
    status: i === projectContents.length - 1 ? 'processing' as const : 'complete' as const,
    created_at: new Date(Date.now() - (projectContents.length - i) * 86400000 * 2).toISOString(),
  }));
};

export const mockEpisodes: Record<string, Episode[]> = Object.fromEntries(
  mockProjects.map(p => [p.project_id, makeEpisodes(p.project_id)])
);

export const mockInsights = (projectId: string, category?: string) => {
  const eps = mockEpisodes[projectId] || [];
  const filtered = category && category !== 'all' ? eps.filter(e => e.category === category) : eps;
  return { episodes: filtered, total: filtered.length };
};

export const mockSearch = (projectId: string, query: string) => {
  const eps = mockEpisodes[projectId] || [];
  const q = query.toLowerCase();
  return eps.filter(e => e.content.toLowerCase().includes(q)).slice(0, 10);
};
