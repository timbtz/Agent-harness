import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { useEffect } from 'react';

export function useProjectGraph(projectId: string | null) {
  const { toast } = useToast();
  const query = useQuery({
    queryKey: ['projectGraph', projectId],
    queryFn: () => api.getProjectGraph(projectId!),
    enabled: !!projectId,
    retry: 2,
    refetchInterval: 5000,
  });
  useEffect(() => {
    if (query.error) toast({ title: 'Failed to load graph', description: String(query.error), variant: 'destructive' });
  }, [query.error]);
  return query;
}
