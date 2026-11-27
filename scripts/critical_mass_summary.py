"""Summarize the critical-mass runs (labels "cm_..._k{k}of{n}") per condition.

    python -m scripts.critical_mass_summary                 # reads results/
    python -m scripts.critical_mass_summary path/to/results --csv cm.csv

For each k (number of committed juniors) it averages over runs:
  * candor of the CAUTIOUS juniors (do they open up?), overall and per round;
  * candor of the COMMITTED juniors (a manipulation check: should stay high);
  * the simulated human's check scores (private_state_expression, agency, human_realism).
All values are the rubric's normalized 0..1 scores. A role is read from the
junior's persona (the stance sentence written by scripts/make_critical_mass.py).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean

from scripts.make_critical_mass import COMMITTED_STANCE

LABEL_RE = re.compile(r"^cm_.*_k(\d+)of(\d+)$")
HUMAN_KEYS = ["private_state_expression", "agency", "human_realism"]


def _avg(values):
    values = [v for v in values if v is not None]
    return mean(values) if values else None


def _fmt(value):
    return "  —  " if value is None else f"{value:5.2f}"


def summarize_run(doc: dict) -> dict | None:
    label = doc.get("label") or doc.get("configuration", {}).get("label") or ""
    match = LABEL_RE.match(label)
    evaluation = doc.get("evaluation") or {}
    scores = evaluation.get("scores")
    if not match or evaluation.get("status") != "completed" or not scores:
        return None
    committed_ids = {
        a["id"] for a in doc["configuration"]["agents"] if COMMITTED_STANCE in (a["persona_agent"].get("ethics") or "")
    }
    by_agent = scores.get("by_agent", {})
    roles = {"committed": [], "cautious": []}
    for agent_id, stats in by_agent.items():
        roles["committed" if agent_id in committed_ids else "cautious"].append((stats.get("by_criterion") or {}).get("candor"))
    cautious_by_round = {}
    for turn in evaluation.get("turns", []):
        values = [
            (detail.get("normalized") or {}).get("candor")
            for agent_id, detail in (turn.get("agents") or {}).items()
            if agent_id not in committed_ids
        ]
        cautious_by_round[turn["round"]] = _avg(values)
    human = (scores.get("human_agent") or {}).get("by_criterion") or {}
    return {
        "k": int(match[1]),
        "n": int(match[2]),
        "committed_candor": _avg(roles["committed"]),
        "cautious_candor": _avg(roles["cautious"]),
        "cautious_by_round": cautious_by_round,
        "overall": (scores.get("overall") or {}).get("discounted"),
        **{f"human_{key}": (human.get(key) or {}).get("discounted") for key in HUMAN_KEYS},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize critical-mass runs.")
    parser.add_argument("directory", nargs="?", default="results", help="folder with result JSON files (default: results)")
    parser.add_argument("--csv", help="also write one row per run to this CSV file")
    args = parser.parse_args()

    runs = []
    for path in sorted(Path(args.directory).glob("*.json")):
        try:
            row = summarize_run(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError):
            continue
        if row:
            runs.append({**row, "file": path.name})
    if not runs:
        print(f"No evaluated critical-mass results (label cm_..._k<k>of<n>) found in {args.directory}/")
        return

    groups = defaultdict(list)
    for row in runs:
        groups[(row["k"], row["n"])].append(row)
    max_round = max(r for row in runs for r in row["cautious_by_round"])
    round_cols = list(range(1, max_round + 1))

    header = (
        f"{'k/n':>5} {'share':>5} {'runs':>4} | {'cautious':>8} "
        + " ".join(f"{'R' + str(r):>5}" for r in round_cols)
        + f" | {'commit':>6} | {'H.priv':>6} {'H.agcy':>6} {'H.real':>6} | {'overall':>7}"
    )
    print("Candor = normalized rubric candor (0..1). cautious = juniors who read the room; R1.. = their candor per round.")
    print("H.* = simulated human check (private_state_expression, agency, human_realism).\n")
    print(header)
    print("-" * len(header))
    for (k, n), rows in sorted(groups.items()):
        cells = [
            f"{k}/{n}".rjust(5),
            f"{k / n:5.0%}",
            f"{len(rows):4d}",
            "|",
            _fmt(_avg([r["cautious_candor"] for r in rows])).rjust(8),
            *(_fmt(_avg([r["cautious_by_round"].get(rnd) for r in rows])) for rnd in round_cols),
            "|",
            _fmt(_avg([r["committed_candor"] for r in rows])).rjust(6),
            "|",
            *(_fmt(_avg([r[f"human_{key}"] for r in rows])).rjust(6) for key in HUMAN_KEYS),
            "|",
            _fmt(_avg([r["overall"] for r in rows])).rjust(7),
        ]
        print(" ".join(cells))

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as handle:
            fields = ["file", "k", "n", "cautious_candor", *[f"cautious_r{r}" for r in round_cols], "committed_candor",
                      *[f"human_{key}" for key in HUMAN_KEYS], "overall"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in sorted(runs, key=lambda r: (r["k"], r["file"])):
                writer.writerow({
                    **{key: row[key] for key in fields if key in row},
                    **{f"cautious_r{r}": row["cautious_by_round"].get(r) for r in round_cols},
                })
        print(f"\nWrote {len(runs)} rows to {args.csv}")


if __name__ == "__main__":
    main()
