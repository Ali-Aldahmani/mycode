import { useEngineStatus } from "@/engine/engine";

/** Small pill showing whether Python + pandas are loaded. */
export function EngineStatusPill() {
  const status = useEngineStatus((s) => s.status);
  if (status.state === "ready") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-300" title={`Loaded in ${(status.ms / 1000).toFixed(1)}s`}>
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Python ready
      </span>
    );
  }
  if (status.state === "error") {
    return (
      <span className="rounded-full bg-red-500/10 px-2.5 py-1 text-xs text-red-300" title={status.message}>
        Python failed to load
      </span>
    );
  }
  const progress = status.state === "loading" ? status.progress : 0;
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-white/5 px-2.5 py-1 text-xs text-neutral-400">
      <span className="relative h-1 w-14 overflow-hidden rounded-full bg-white/10">
        <span className="absolute inset-y-0 left-0 rounded-full bg-amber-400 transition-all duration-500" style={{ width: `${Math.round(progress * 100)}%` }} />
      </span>
      {status.state === "loading" ? status.message : "Starting"}…
    </span>
  );
}
