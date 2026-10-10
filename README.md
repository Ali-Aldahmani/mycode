# Pandas Visual Trainer

Learn pandas by watching it work. You write pandas code, it runs **in your
browser** (Pyodide in a Web Worker), and a stage animates what your code
actually did: rows fade out, slide, cluster and collapse, tables connect,
cells move. 49 challenges, easy to hard, each one unlocking the next.

```
/frontend     Vite + React + TS: the visual engine (player), challenge screen, path screen
/backend      FastAPI + SQLAlchemy + Alembic: challenges, submissions, scores, progress
/pyengine     the Python half of the visual engine (runs in Pyodide AND on the backend)
/challenges   one JSON seed file per challenge (49)
docker-compose.yml
```

`/pyengine` is the one addition to the planned layout: the tracer, frame
generator and checker are Python, and both the browser (Pyodide) and the
backend validator must run the *same* code, so it lives in one shared place.

---

## Running it

### 1. API + database

With Docker:

```bash
docker compose up --build
```

This starts Postgres and the API on http://localhost:8000. The API container
runs the migrations, validates and seeds the challenges, then serves.

Without Docker (SQLite file, no Postgres needed):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
export DATABASE_URL=sqlite:///./dev.db                # Windows PowerShell: $env:DATABASE_URL="sqlite:///./dev.db"
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload --reload-dir app --reload-dir ../pyengine
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api/*` to
`http://localhost:8000` (override with `API_URL=...`). Pyodide 314.0.7 and
pandas are loaded from the jsDelivr CDN in the background as soon as the app
opens (about 5-10 s on the first visit, cached afterwards).

| Page | What it is |
| --- | --- |
| `/` | The path: 49 challenges by level, lock state, best scores, averages per category |
| `/c/<slug>` | A challenge: description, hints, submissions, editor, animated result |
| `/lab` | The engine lab (Phase 1 prototype): sample operations on hard-coded tables, live mode |

### Tests and checks

```bash
cd backend
pytest                                   # API flow, scoring, validation, engine primitives (35 tests)
python -m scripts.validate_challenges    # validates every file in /challenges
cd ../frontend && npm run typecheck
```

---

## Architecture

```
 browser                                                        backend
┌──────────────────────────────────────────────────────┐      ┌──────────────────┐
│ Monaco ──code──► Runner (Pyodide worker, Comlink)    │      │ FastAPI          │
│                    └─ pyengine: tracer → frames      │      │  challenges      │
│                    └─ pyengine: checker (diff)       │      │  submissions ◄───┼── facts only
│ Player ◄──frames── (all frames generated once)       │──────►  progress        │   (status, help,
│   layout → Stage (Framer Motion, transform/opacity)  │ POST │  users           │    code)
└──────────────────────────────────────────────────────┘      │ pyengine: validate│
                                                              └──────────────────┘
```

* **User code never goes to the backend for execution.** Submit runs the code
  in the worker, plays the animation immediately, checks the result in the
  worker, and posts the facts (status, help used, code) to the backend *in
  parallel*. The visual never waits for the network.
* **Runner**: `run(code, inputs) → output | error` (`frontend/src/engine/types.ts`).
  v1: `PyodideRunner` in `frontend/src/engine/engine.ts`.
* **Checker**: `check(output, target, options) → pass/fail + diff`. v1:
  `pandas_equal` (`pyengine/checker.py`, called through the worker).
* Runners and checkers are looked up by the challenge's `language` and
  `checker_type`; challenges also carry `library`, `visual_type` and `source`.
* **Backend modules** (`backend/app/<module>/{models,schemas,service,routes}.py`):
  `core`, `users`, `challenges`, `submissions`, `progress`. New features
  (auth, community, ai_judge, mcp) are new folders; `users/deps.py:current_user`
  is the single seam where real authentication plugs in.
* **Scoring lives only in `backend/app/submissions/scoring.py`.** The browser
  sends facts; the backend computes points.

---

## The frame format

Everything visual is a list of frames, and one generic player plays them. The
contract has exactly two definitions:

* TypeScript: `frontend/src/engine/frames.ts`
* Python: `pyengine/contract.py` (the only place frames are built)

```ts
interface Frame {
  index: number;          // position in the run
  stage: number;          // 0 = input, then one stage per code step
  primitive: Primitive;   // show | fade_out | slide | appear | scan | cluster | collapse | connect | move_cells
  label: string;          // "Keep rows where the condition is True: 2 rows out"
  tables: TableState[];   // the full state of every table on stage (a snapshot)
  links: Link[];          // SVG lines (connect)
  code: CodeRange | null; // the part of the user's code this frame belongs to
  duration: number;       // ms at 1x
}
interface TableState { id; title; kind: "dataframe"|"series"|"scalar"; slot: [col,row];
                       columns: ColumnState[]; rows: RowState[]; ghosts?: Ghost[]; ... }
interface RowState   { id: "df:3"; label; color; cells: (string|null)[];
                       mark?; group?; gapBefore?; cellMarks?; cellKeys?; origins?; scan?; ... }
```

**Element keys** tie frames together. Every badge, header and cell gets a key
(`"<rowId>|<colId>"`, `"badge:<rowId>"`, `"hdr:<table>:<col>"`). Same key in
the next frame means the element *moves*, a new key *appears*, and a missing
key *fades out*. Three extras cover the harder moves:

* `cellKeys`: this cell *is* an element from the previous frame (melt, concat:
  the value cell physically travels).
* `origins`: this new cell flies in from another element (merge: result cells
  come from their source cells).
* `ghosts`: an old element folds onto a target and disappears (groupby collapse,
  reductions, pivot_table aggregation).

Every frame is a full snapshot, so stepping in either direction costs nothing.

### How a run becomes frames

1. **Tracer** (`pyengine/tracer.py`) runs the user's code statement by
   statement. Method chains are split into links and each link is evaluated
   once (`df[df.age > 30].groupby('city')['salary'].mean()` → filter, then
   groupby/select/mean). Non-displayable intermediates (GroupBy, `.str`,
   `.loc`) merge into the next link. Other statements (`df['x'] = ...`,
   `inplace=True`) become *mutation* stages by diffing variables before and
   after. Each stage stores its code range for Monaco highlighting.
2. **Row identity**: inputs get a clean RangeIndex; that label is the row id
   (`df:3`) and the source of its stable colour. If a stage keeps index labels
   (filter, sort, new column, fillna...), a generic diff produces fade_out,
   slide, appear and scan frames.
3. When identity can't be tracked, operation-specific generators use
   **provenance**: they re-run the operation with hidden position columns to
   learn which input cells made which output cells (merge, concat, melt), or
   read it from pandas (`GroupBy.indices`, pivot labels). That gives cluster
   and collapse, connect, and move_cells.
4. Anything else cross-fades to the result, tagged with the challenge's
   `visual_type`.

Over 20 rows (or 12 columns), visual mode switches off and the result is shown
without animation.

### Adding a frame generator

A generator turns traced stages into frames using `pyengine/contract.py`. The
pandas one is `PandasFrameGenerator`. A different family (for example, Python
loop tracing) adds its own module that emits the same `Frame` dicts: the
player, layout and controls don't change. Register it next to the pandas one
in `pyengine/runner.py`.

### Visual language

* Row badge = identity colour that follows the row everywhere. Column headers
  have their own colours, so new and dropped columns stand out.
* **Green** kept/matched/new · **red** removed/wrong · **yellow** changed ·
  **gray** NaN · blue outline = the column the operation looks at.
* Playback: play/pause (space), step (←/→), replay (r), speed from 0.25x to
  **instant** (jump to the end state).

---

## Adding a challenge

1. Create `challenges/NN-my-slug.json`:

```jsonc
{
  "slug": "boolean-filter", "order": 8, "level": 2,
  "title": "Filter rows", "method": "boolean mask", "category": "Pick",
  "language": "python", "library": "pandas", "source": "official",
  "task": "Keep only the products that cost more than 20.",
  "inputs": { "df": { "type": "dataframe", "columns": ["name", "price"], "data": [["Desk", 120], ["Pen", 2]] } },
  "target": { "...": "filled in by build_target" },
  "starter_code": "result = ",
  "hint_1": "You need to keep only some rows based on a condition.",   // direction, no syntax
  "hint_2": "result = df[df[___] ___ ___]",                            // pattern with blanks
  "example": { "inputs": { "cities": { "...": "different data" } }, "code": "result = cities[cities['population'] > 3]" },
  "reference_solution": "result = df[df['price'] > 20]",
  "why": "Shown after a correct answer.",
  "docs_url": "https://pandas.pydata.org/docs/user_guide/indexing.html#boolean-indexing",
  "checker_type": "pandas_equal",
  "checker_options": { "check_row_order": false },
  "visual_type": "fade_out"
}
```

   Value specs: `{"type": "dataframe", "columns", "data", "index"?, "index_name"?, "dtypes"?}`,
   `{"type": "series", "name", "data", "index"?}`, `{"type": "scalar", "value", "tuple"?}`.
   `null` means NaN. List labels become MultiIndex tuples.
   Checker options: `check_row_order`, `check_column_order`, `check_index`,
   `check_dtype` (compares families: integer, float, text...), `check_names`, `rtol`.

2. Fill the target from the reference solution, then **read it**:

```bash
cd backend
python -m scripts.build_target ../challenges/NN-my-slug.json --write
```

3. Validate and seed:

```bash
python -m scripts.validate_challenges
python -m scripts.seed
```

   The validator checks the schema, runs the reference solution with real
   pandas through `/pyengine` (the code the browser runs) and compares it to the
   target with the challenge's own checker options. It also checks that hint 2
   has blanks and isn't the solution, that the example runs on different data,
   that slugs and orders are unique, and that the docs link is on
   pandas.pydata.org. Invalid files are reported and never seeded.

---

## Scoring

* Each challenge starts at 100.
* Example −15, Hint 1 −20, Hint 2 −35: each charged once per round, with the
  cost shown on the button. Opening help is recorded on the server, so a
  reload doesn't make it free.
* Wrong answers: the first two are free, then −5 each, capped at −20.
* Errors (exceptions, no `result`) are shown but are not attempts.
* The docs link is always free.
* After solving, you can retry: each retry is a new round, and the best score
  is kept. Every submission stores which help was used.

---

## Design notes and deviations

* **Computed layout instead of measured `layout`/`layoutId`.** The spec
  suggested Framer Motion `layout` + `layoutId`. The player keeps Framer
  Motion and `AnimatePresence`, but positions come from a pure layout function
  (`frontend/src/engine/player/layout.ts`) instead of DOM measurement (FLIP).
  Reasons: SVG links and cells moving between tables need exact coordinates up
  front; every frame's geometry can be precomputed once per run (stepping is
  free); column widths stay fixed across a run (no jitter); and only
  `transform`/`opacity` animate. Element keys play the role `layoutId` would
  have.
* **Display tables come from the backend.** The Description tab's input and
  target tables are rendered by `/pyengine` on the server with real pandas, so
  they appear instantly (before Pyodide finishes loading) and look exactly
  like the stage (`34.0` in a float column, which JSON can't express).
* **Trust model.** The backend records what the browser reports (correct /
  wrong), as the "user code runs in the browser only" rule requires. Fine for
  a personal tool; when the app is published, the planned `ai_judge` or a
  server-side re-check of the stored code is the place to verify claims.
* **Stale runs.** Python can't be interrupted mid-statement without
  cross-origin isolation, so stale playground runs are skipped before they
  start and their results are dropped if they finish late. A run over 10 s
  terminates and restarts the worker.
* **Targets were generated, then reviewed.** The 49 targets were produced by
  running each reference solution (`build_target`) and checked by hand against
  their tasks. Alternative correct answers (e.g. `pd.merge(left, right)`,
  `df.assign(...)`, `astype(int)`, `groupby(...).size()` for value counts)
  were tested to pass, and common wrong answers to fail.
