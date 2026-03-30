import { ArrowLeft, Hexagon, List, Search as SearchIcon, Clock, Sparkles } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { HealthIndicator } from './HealthIndicator';
import { ProjectList } from './ProjectList';
import { EpisodeList } from './EpisodeList';
import { SearchPanel } from './SearchPanel';
import { TimelinePanel } from './TimelinePanel';
import type { Project } from '@/lib/types';

interface Props {
  selectedProject: Project | null;
  onSelectProject: (project: Project | null) => void;
  onNavigateToEpisode?: (episodeId: string) => void;
  onNavigateToEntity?: (entityName: string) => void;
}

export function LeftPanel({ selectedProject, onSelectProject, onNavigateToEpisode, onNavigateToEntity }: Props) {
  return (
    <div className="w-80 shrink-0 border-r border-border/30 glass flex flex-col h-screen relative">
      {/* Subtle warm edge glow */}
      <div className="absolute top-0 right-0 w-px h-full bg-gradient-to-b from-primary/10 via-transparent to-accent/10" />

      {/* Header */}
      <div className="p-6 border-b border-border/20">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Hexagon className="h-7 w-7 text-primary" strokeWidth={1.5} />
            <Sparkles className="h-3 w-3 text-primary absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
          </div>
          <div>
            <h1 className="text-xl font-display font-semibold text-gradient leading-tight">Agent Harness</h1>
            <p className="text-[11px] text-muted-foreground tracking-[0.25em] uppercase mt-0.5">Knowledge Graphs</p>
          </div>
        </div>
      </div>

      {/* Health */}
      <div className="px-5 py-3 border-b border-border/20">
        <HealthIndicator />
      </div>

      {/* Content */}
      <ScrollArea className="flex-1 scrollbar-thin">
        <div className="p-5">
          {selectedProject ? (
            <div className="space-y-5">
              <button
                onClick={() => onSelectProject(null)}
                className="glass-button flex items-center gap-2 text-sm text-foreground/70 hover:text-foreground px-4 py-2 rounded-full"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                Back to projects
              </button>

              <div className="space-y-2 p-4 rounded-xl bg-secondary/20 border border-border/20">
                <h2 className="text-lg font-display font-semibold text-foreground">{selectedProject.name}</h2>
                {selectedProject.description && (
                  <p className="text-sm text-muted-foreground leading-relaxed">{selectedProject.description}</p>
                )}
              </div>

              <Tabs defaultValue="episodes" className="w-full">
                <TabsList className="w-full h-10 bg-secondary/20 border border-border/20 p-0.5 rounded-full">
                  <TabsTrigger value="episodes" className="text-xs flex-1 gap-1.5 rounded-full data-[state=active]:bg-primary/10 data-[state=active]:text-primary">
                    <List className="h-3.5 w-3.5" />
                    Episodes
                  </TabsTrigger>
                  <TabsTrigger value="search" className="text-xs flex-1 gap-1.5 rounded-full data-[state=active]:bg-primary/10 data-[state=active]:text-primary">
                    <SearchIcon className="h-3.5 w-3.5" />
                    Search
                  </TabsTrigger>
                  <TabsTrigger value="timeline" className="text-xs flex-1 gap-1.5 rounded-full data-[state=active]:bg-primary/10 data-[state=active]:text-primary">
                    <Clock className="h-3.5 w-3.5" />
                    Timeline
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="episodes">
                  <EpisodeList projectId={selectedProject.project_id} onSelectEpisode={onNavigateToEpisode} />
                </TabsContent>
                <TabsContent value="search">
                  <SearchPanel projectId={selectedProject.project_id} onSelectResult={onNavigateToEntity} />
                </TabsContent>
                <TabsContent value="timeline">
                  <TimelinePanel projectId={selectedProject.project_id} onSelectEpisode={onNavigateToEpisode} />
                </TabsContent>
              </Tabs>
            </div>
          ) : (
            <div className="space-y-4">
              <h2 className="text-sm tracking-[0.2em] text-muted-foreground uppercase">Active Projects</h2>
              <ProjectList onSelect={onSelectProject} />
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
