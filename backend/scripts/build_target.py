"""Authoring helper: print (or write) a challenge's target from its reference
solution, run with real pandas through the shared engine.

    python -m scripts.build_target ../challenges/08-boolean-filter.json          # print
    python -m scripts.build_target ../challenges/08-boolean-filter.json --write  # update the file

Always read the printed target before trusting it: the validator can only
check that the solution and the target agree, not that the target is what the
task asks for.
"""
import argparse
import json
import sys
from pathlib import Path

from app.core.pyengine import runner


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.file.read_text(encoding="utf-8"))
    res = runner.run(data["reference_solution"], data["inputs"], run_id="build")
    if not res["ok"]:
        print(f"reference_solution fails: {res['error']}", file=sys.stderr)
        return 1
    print(json.dumps(res["result"], indent=2, ensure_ascii=False))
    print("frames:", " ".join(f["primitive"] for f in res["frames"]), file=sys.stderr)
    if args.write:
        data["target"] = res["result"]
        args.file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote target to {args.file}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
