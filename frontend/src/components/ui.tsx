import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "success" | "ghost" | "subtle" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-amber-500 text-black hover:bg-amber-400",
  success: "bg-emerald-600 text-white hover:bg-emerald-500",
  ghost: "text-neutral-300 hover:bg-white/10 hover:text-white",
  subtle: "bg-white/[0.06] text-neutral-200 hover:bg-white/[0.12]",
  danger: "bg-red-500/15 text-red-300 hover:bg-red-500/25",
};

export function Button({
  variant = "subtle",
  size = "md",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md" }) {
  const sz = size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3.5 text-sm";
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${sz} ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  right,
}: {
  tabs: { id: T; label: ReactNode }[];
  value: T;
  onChange: (t: T) => void;
  right?: ReactNode;
}) {
  return (
    <div className="flex h-10 shrink-0 items-center gap-1 border-b border-white/5 bg-panel-2/60 px-2">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`relative h-10 px-3 text-sm transition-colors ${
            value === t.id ? "text-white" : "text-neutral-400 hover:text-neutral-200"
          }`}
        >
          {t.label}
          {value === t.id && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-amber-400" />}
        </button>
      ))}
      <div className="flex-1" />
      {right}
    </div>
  );
}

export function StatusPill({ status }: { status: "correct" | "wrong" | "error" }) {
  const map = {
    correct: "bg-emerald-500/15 text-emerald-300",
    wrong: "bg-red-500/15 text-red-300",
    error: "bg-neutral-500/20 text-neutral-300",
  } as const;
  const label = { correct: "Accepted", wrong: "Wrong answer", error: "Error" }[status];
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${map[status]}`}>{label}</span>;
}

export function scoreColor(score: number | null | undefined): string {
  if (score == null) return "text-neutral-500";
  if (score >= 90) return "text-emerald-300";
  if (score >= 60) return "text-amber-300";
  return "text-orange-300";
}

export function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

/** Renders `inline code` and **bold** in short task/hint strings. */
export function RichText({ text }: { text: string }) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith("`") && p.endsWith("`") ? (
          <code key={i} className="rounded bg-white/[0.07] px-1.5 py-0.5 font-mono text-[0.85em] text-amber-200">
            {p.slice(1, -1)}
          </code>
        ) : p.startsWith("**") && p.endsWith("**") ? (
          <strong key={i} className="font-semibold text-white">
            {p.slice(2, -2)}
          </strong>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}
