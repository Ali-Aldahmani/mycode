import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { HelpKind, SubmissionIn } from "./types";

export const keys = {
  path: ["challenges"] as const,
  challenge: (slug: string) => ["challenge", slug] as const,
  solution: (slug: string) => ["challenge", slug, "solution"] as const,
  submissions: (slug: string) => ["submissions", slug] as const,
  progress: ["progress"] as const,
};

export const useChallenges = () => useQuery({ queryKey: keys.path, queryFn: api.challenges });

export const useChallenge = (slug: string) =>
  useQuery({ queryKey: keys.challenge(slug), queryFn: () => api.challenge(slug), staleTime: 60_000 });

/** The reference solution, available once the user has submitted. */
export const useSolution = (slug: string, enabled: boolean) =>
  useQuery({
    queryKey: keys.solution(slug),
    queryFn: async () => (await api.challenge(slug, true)).reference_solution,
    enabled,
  });

export const useSubmissions = (slug: string) =>
  useQuery({ queryKey: keys.submissions(slug), queryFn: () => api.submissions(slug) });

export const useProgress = () => useQuery({ queryKey: keys.progress, queryFn: api.progress });

export function useSubmit(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SubmissionIn) => api.submit(body),
    onSuccess: (res) => {
      void qc.invalidateQueries({ queryKey: keys.submissions(slug) });
      void qc.invalidateQueries({ queryKey: keys.path });
      void qc.invalidateQueries({ queryKey: keys.progress });
      void qc.invalidateQueries({ queryKey: keys.solution(slug) });
      qc.setQueryData(keys.challenge(slug), (old: Awaited<ReturnType<typeof api.challenge>> | undefined) =>
        old
          ? {
              ...old,
              solved: res.progress.solved,
              best_score: res.progress.best_score,
              submitted: old.submitted || res.submission.status !== "error",
              help_used: res.progress.help_used,
              potential: res.potential,
            }
          : old,
      );
      if (res.next_slug) void qc.invalidateQueries({ queryKey: keys.challenge(res.next_slug) });
    },
  });
}

export function useOpenHelp(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (kind: HelpKind) => api.openHelp(slug, kind),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.challenge(slug) }),
  });
}
