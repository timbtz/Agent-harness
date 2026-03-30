import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import { LeftPanel } from '@/components/LeftPanel';
import { GraphView } from '@/components/GraphView';
import { useProjectGraph } from '@/hooks/useProjectGraph';
import type { Project } from '@/lib/types';

const queryClient = new QueryClient();

function Dashboard() {
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [navTarget, setNavTarget] = useState<string | null>(null);
  const { data: graphData } = useProjectGraph(selectedProject?.project_id ?? null);

  function handleNavigateToEpisode(episodeId: string) {
    const node = graphData?.nodes.find(n => n.name === `ep-${episodeId}`);
    if (node) setNavTarget(node.id);
  }

  function handleNavigateToEntity(entityName: string) {
    // Search results: id is entity_name for graph-backed results
    const node = graphData?.nodes.find(n => n.name === entityName);
    if (node) setNavTarget(node.id);
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <LeftPanel
        selectedProject={selectedProject}
        onSelectProject={setSelectedProject}
        onNavigateToEpisode={handleNavigateToEpisode}
        onNavigateToEntity={handleNavigateToEntity}
      />
      <GraphView
        selectedProject={selectedProject}
        onSelectProject={setSelectedProject}
        externalNavTarget={navTarget}
        onNavHandled={() => setNavTarget(null)}
      />
    </div>
  );
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Dashboard />
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
