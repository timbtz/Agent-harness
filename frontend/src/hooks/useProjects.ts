import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { useEffect } from 'react';

export function useHealth() {
  const { toast } = useToast();
  const query = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: 30000,
    retry: 1,
  });
  useEffect(() => {
    if (query.error) toast({ title: 'Health check failed', description: String(query.error), variant: 'destructive' });
  }, [query.error]);
  return query;
}

export function useProjects() {
  const { toast } = useToast();
  const query = useQuery({
    queryKey: ['projects'],
    queryFn: api.getProjects,
    retry: 2,
  });
  useEffect(() => {
    if (query.error) toast({ title: 'Failed to load projects', description: String(query.error), variant: 'destructive' });
  }, [query.error]);
  return query;
}
