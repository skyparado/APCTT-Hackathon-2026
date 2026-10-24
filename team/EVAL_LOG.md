# Evaluation log

One line per run, newest first. Part A is the official TRL score (exact 1.0, off by one 0.5,
abstain 0.25). **Only the held-out number is honest**: `data/cases` was used to write and tune the
TRL cues, `data/heldout` was labelled (commit b4c7308) before the module ever ran on it.

Held-out rule: never change code because of a held-out miss. When the held-out set has been used
to make a decision, collect a fresh one.

| Date | Code | Set | Cases | Mean A | Exact | B | Slowest case | Notes |
|---|---|---|---|---|---|---|---|---|
| 2026-10-24 | 165d015 | **held-out** | 5 | **0.400** | 1/5 | 0.333 | 1.4 s | always-abstain baseline 0.250 on this set |
| 2026-10-24 | 0c0cafe | dev (`data/cases`) | 16 | 0.781 | 12/16 | 0.333 | 0.4 s | after tightening cues on these cases |
| 2026-10-24 | 070beea | dev (`data/cases`) | 16 | 0.625 | 9/16 | 0.333 | 0.4 s | first real run, whole reports |
| 2026-10-24 | 070beea | dev, gold quotes only (`team/eval_trl.py`) | 16 | 0.969 | 15/16 | n/a | n/a | upper bound: perfect retrieval |

B stays at 0.333 while no criterion is ever marked `met` (the criterion judge, Task 11, is not in yet).

## Why the held-out misses happen (diagnosis only, not tuned)

| Failure | Example | What would fix it |
|---|---|---|
| Evidence about predecessor technology | HiVHAc rated 8 from a sentence about the NASA-77M thruster | judge whether the sentence is about the assessed target |
| Goals phrased without "will" | "The short term goal is a microsat flight test." | judge whether the event happened (stance) |
| Conference-paper title and author block | "...Sounding Rocket One Flight Test Jake A." | skip front matter by layout, not report number |
| Relevant vs operational flight | suborbital sounding rocket counted as operational | meaning, not keywords |

All four point to an entailment judge (catalogue `deberta-v3-base-zeroshot-v2.0-c`) asking "does this
sentence report a completed test of the target?", which belongs in the criterion judge (Task 11).
