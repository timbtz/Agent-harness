import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { useEffect } from 'react';

export function useProjectInsights(projectId: string | null, category?: string) {
  const { toast } = useToast();
  const query = useQuery({
    queryKey: ['insights', projectId, category],
    queryFn: () => api.getProjectInsights(projectId!, 1, 50, category),
    enabled: !!projectId,
    refetchInterval: 5000,
  });
  useEffect(() => {
    if (query.error) toast({ title: 'Failed to load episodes', variant: 'destructive' });
  }, [query.error]);
  return query;
}

export function useProjectTimeline(projectId: string | null) {
  return useQuery({
    queryKey: ['timeline', projectId],
    queryFn: () => api.getProjectTimeline(projectId!),
    enabled: !!projectId,
  });
}

export function useSearchProject(projectId: string | null) {
  const { toast } = useToast();
  return useMutation({
    mutationFn: ({ query, limit }: { query: string; limit: number }) =>
      api.searchProject(projectId!, query, limit),
    onError: () => toast({ title: 'Search failed', variant: 'destructive' }),
  });
}

export function useDeleteEpisode() {
  const qc = useQueryClient();
  const { toast } = useToast();
  return useMutation({
    mutationFn: ({ projectId, episodeId }: { projectId: string; episodeId: string }) =>
      api.deleteEpisode(projectId, episodeId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['insights'] });
      toast({ title: 'Episode deleted' });
    },
    onError: () => toast({ title: 'Delete failed', variant: 'destructive' }),
  });
}
