"""pyengine: the Python half of the visual engine.

Runs in the browser (Pyodide web worker) and on the backend (challenge
validation, tests). Pure Python + pandas, no I/O.

    contract.py       frame format builders (mirrors frontend/src/engine/frames.ts)
    tracer.py         runs user code, records stages
    pandas_frames.py  frame generator for pandas table transforms
    checker.py        "pandas_equal" checker + diff tables
    valuespec.py      JSON <-> pandas values, display formatting
    runner.py         entry points used by the worker
"""
