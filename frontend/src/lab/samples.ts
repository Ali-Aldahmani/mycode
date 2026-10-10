import type { Inputs } from "@/engine/types";

/** Tiny hard-coded tables for the engine lab. */
export const DATA: Inputs = {
  df: {
    type: "dataframe",
    columns: ["name", "city", "age", "salary"],
    data: [
      ["Ana", "Paris", 34, 52000],
      ["Ben", "Lyon", 28, null],
      ["Cleo", "Paris", 45, 61000],
      ["Dev", "Nice", 31, 48000],
      ["Eli", "Lyon", null, 39000],
      ["Fay", "Paris", 29, 55000],
    ],
  },
  left: {
    type: "dataframe",
    columns: ["emp", "dept_id"],
    data: [
      ["Ana", 1],
      ["Ben", 2],
      ["Cleo", 1],
      ["Dev", 3],
    ],
  },
  right: {
    type: "dataframe",
    columns: ["dept_id", "dept"],
    data: [
      [1, "Sales"],
      [2, "IT"],
      [4, "HR"],
    ],
  },
  scores: {
    type: "dataframe",
    columns: ["student", "math", "art"],
    data: [
      ["Ana", 90, 75],
      ["Ben", 68, 88],
      ["Cleo", 82, 91],
    ],
  },
  sales: {
    type: "dataframe",
    columns: ["day", "store", "units"],
    data: [
      ["Mon", "A", 3],
      ["Mon", "B", 5],
      ["Tue", "A", 4],
      ["Tue", "B", 2],
      ["Wed", "A", 6],
      ["Wed", "B", 1],
    ],
  },
};

export interface Sample {
  id: string;
  title: string;
  primitive: string;
  code: string;
  inputs: string[];
}

export const SAMPLES: Sample[] = [
  { id: "filter", title: "Filter", primitive: "fade out", inputs: ["df"], code: "result = df[df['age'] > 30]" },
  { id: "sort", title: "Sort", primitive: "slide", inputs: ["df"], code: "result = df.sort_values('salary', ascending=False)" },
  { id: "add", title: "Add column", primitive: "scan + appear", inputs: ["df"], code: "df['bonus'] = df['salary'] * 0.1\nresult = df" },
  { id: "dropna", title: "dropna", primitive: "fade out", inputs: ["df"], code: "result = df.dropna()" },
  { id: "fillna", title: "fillna", primitive: "appear", inputs: ["df"], code: "result = df.fillna({'age': 30, 'salary': 0})" },
  { id: "str", title: ".str.upper", primitive: "scan", inputs: ["df"], code: "result = df['city'].str.upper()" },
  { id: "groupby", title: "groupby + sum", primitive: "cluster + collapse", inputs: ["df"], code: "result = df.groupby('city')['salary'].sum()" },
  { id: "merge", title: "merge", primitive: "connect", inputs: ["left", "right"], code: "result = left.merge(right, on='dept_id', how='left')" },
  { id: "melt", title: "melt", primitive: "move cells", inputs: ["scores"], code: "result = scores.melt(id_vars='student', var_name='subject', value_name='score')" },
  { id: "pivot", title: "pivot", primitive: "move cells", inputs: ["sales"], code: "result = sales.pivot(index='day', columns='store', values='units')" },
  {
    id: "chain",
    title: "Chained",
    primitive: "filter → group → mean",
    inputs: ["df"],
    code: "result = df[df.age > 30].groupby('city')['salary'].mean()",
  },
  { id: "mean", title: "Reduce", primitive: "scan + collapse", inputs: ["df"], code: "result = df['salary'].mean()" },
];

export function inputsFor(names: string[]): Inputs {
  return Object.fromEntries(names.map((n) => [n, DATA[n]]));
}
