import type { Inputs, ValueSpec } from "@/engine/types";

/** Parse what the user typed into a JSON value: number, bool, null (NaN) or text. */
function parseCell(text: string, previous: unknown): unknown {
  const t = text.trim();
  if (t === "" || t === "NaN" || t === "None" || t === "null") return null;
  if (t === "True" || t === "true") return true;
  if (t === "False" || t === "false") return false;
  if (/^-?\d+(\.\d+)?(e-?\d+)?$/i.test(t) && typeof previous !== "string") return Number(t);
  if (/^-?\d+(\.\d+)?$/.test(t) && typeof previous === "string" && previous !== "" && !Number.isNaN(Number(previous))) {
    return t; // a text column that holds digits stays text
  }
  return t;
}

const show = (v: unknown) => (v === null || v === undefined ? "NaN" : String(v));

function Grid({ name, spec, onChange }: { name: string; spec: ValueSpec; onChange: (s: ValueSpec) => void }) {
  if (spec.type === "scalar") return null;
  const isFrame = spec.type === "dataframe";
  const columns = isFrame ? spec.columns.map(String) : [String(spec.name ?? "value")];
  const rows: unknown[][] = isFrame ? spec.data : spec.data.map((v) => [v]);
  const labels = spec.index ?? rows.map((_, i) => i);
  const edit = (r: number, c: number, text: string) => {
    const next = rows.map((row) => [...row]);
    next[r][c] = parseCell(text, rows[r][c]);
    onChange(isFrame ? { ...spec, data: next } : { ...spec, data: next.map((row) => row[0]) });
  };
  return (
    <div className="min-w-0">
      <div className="mb-1 text-[10.5px] font-semibold uppercase tracking-wider text-neutral-500">{name}</div>
      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-0.5 font-mono text-xs">
          <thead>
            <tr>
              <th />
              {columns.map((c) => (
                <th key={c} className="px-2 py-1 text-left font-semibold text-neutral-300">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, r) => (
              <tr key={r}>
                <td className="px-2 text-center text-neutral-500">{show(labels[r])}</td>
                {row.map((v, c) => (
                  <td key={c}>
                    <input
                      defaultValue={show(v)}
                      onChange={(e) => edit(r, c, e.target.value)}
                      className={`w-24 rounded border border-white/10 bg-[#262626] px-2 py-1 outline-none focus:border-amber-400/70 ${
                        v === null ? "italic text-neutral-500" : "text-neutral-200"
                      }`}
                      spellCheck={false}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Playground: every input cell is editable. Empty or "NaN" means missing. */
export function EditableInputs({ inputs, onChange, version }: { inputs: Inputs; onChange: (i: Inputs) => void; version: number }) {
  return (
    <div key={version} className="flex flex-wrap gap-6">
      {Object.entries(inputs).map(([name, spec]) => (
        <Grid key={name} name={name} spec={spec} onChange={(s) => onChange({ ...inputs, [name]: s })} />
      ))}
    </div>
  );
}
