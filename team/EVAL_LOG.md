# Evaluation log

One line per run, newest first. Part A is the official TRL score (exact 1.0, off by one 0.5,
abstain 0.25). **Only the held-out number is honest**: `data/cases` was used to write and tune the
TRL cues, `data/heldout` was labelled (commit 2352e96) before the module ever ran on it.

Held-out rule: never change code because of a held-out miss. When the held-out set has been used
to make a decision, collect a fresh one.

| Date | Code | Set | Cases | Mean A | Exact | B | Slowest case | Notes |
|---|---|---|---|---|---|---|---|---|
| 2026-11-02 | full-pipeline | USGS even, draft labels (`team/eval_judge.py`) | 3 | n/a | n/a | **0.788** | 58 s | thresholds not tuned on these; 30 labelled criteria, labels unreviewed |
| 2026-11-02 | full-pipeline | USGS odd, draft labels (`team/eval_judge.py`) | 6 | n/a | n/a | 0.675 | 42 s | thresholds set on these; 51 labelled criteria |
| 2026-11-02 | full-pipeline | USGS all (`team/eval_public.py`) | 99 | 0.778 | 59/99 | n/a | n/a | TRL rule unchanged, judge results not used for the TRL; always-6 is 0.753 |
| 2026-11-02 | full-pipeline | held-out | 4 of 5 | 0.375 | 0/4 | 0.371 | 40 s | quotes 34/34; judge on. Not-established part fell to 0.71 |
| 2026-11-02 | full-pipeline | dev (`data/cases`) | 16 | 0.688 | 10/16 | 0.442 | 61 s | quotes 128/128; judge on |
| 2026-11-02 | usgs-default | USGS even (`team/eval_public.py`) | 50 | 0.770 | 30/50 | n/a | 1.2 s | run once, after the rule was fixed on the odd fold; always-6 is 0.750. Organizer's estimates, not expert labels |
| 2026-11-02 | usgs-default | USGS odd (`team/eval_public.py`) | 49 | 0.786 | 29/49 | n/a | 2.0 s | fold the rule was chosen on; always-6 is 0.755. All 99 before this rule: 0.076 |
| 2026-11-02 | usgs-default | held-out | 4 of 5 | 0.375 | 0/4 | 0.333 | 0.2 s | total 1.5, down from 2.0 on the same 4 cases: accepted, see below |
| 2026-11-02 | usgs-default | dev (`data/cases`) | 16 | 0.688 | 10/16 | 0.333 | 0.3 s | down from 0.781: accepted, see below |
| 2026-11-02 | 9408880 | **held-out** | 4 of 5 | 0.500 | 1/4 | 0.333 | 0.2 s | kit 0.5, official checklist. NTRS-20160009293 not run (its PDF is not in git), so not comparable with 0.400: the 4 cases total 2.0, the same total as that run |
| 2026-11-02 | 9408880 | dev (`data/cases`) | 16 | 0.781 | 12/16 | 0.333 | 0.3 s | kit 0.5, official checklist: same as 0c0cafe |
| 2026-10-24 | ae81b72 | **held-out** | 5 | **0.400** | 1/5 | 0.333 | 1.4 s | always-abstain baseline 0.250 on this set |
| 2026-10-24 | 0c0cafe | dev (`data/cases`) | 16 | 0.781 | 12/16 | 0.333 | 0.4 s | after tightening cues on these cases |
| 2026-10-24 | 070beea | dev (`data/cases`) | 16 | 0.625 | 9/16 | 0.333 | 0.4 s | first real run, whole reports |
| 2026-10-24 | 070beea | dev, gold quotes only (`team/eval_trl.py`) | 16 | 0.969 | 15/16 | n/a | n/a | upper bound: perfect retrieval |

B was 0.333 while no criterion was ever marked `met`, before the criterion judge (Task 11).
From 2026-11-02 B is scored on the official criteria labelled so far (see `data/README.md`), not all 12.

**Which set to watch.** The hidden cases are USGS-type reports (PROBLEM_DESCRIPTION 12.1), so the USGS
folds are the closest thing to them, even though their labels are only estimates. The NASA sets are
mostly hardware reports. The `usgs-default` rule gives `technology` TRL 6 and `system` TRL 7 instead of
reading the cues, which costs the NASA sets (their `technology` and `system` cases span TRL 2-7) and
is a default, not an assessment: its ceiling is about what always-6 scores until the judge replaces it.

## Why the held-out misses happen (diagnosis only, not tuned)

| Failure | Example | What would fix it |
|---|---|---|
| Evidence about predecessor technology | HiVHAc rated 8 from a sentence about the NASA-77M thruster | judge whether the sentence is about the assessed target |
| Goals phrased without "will" | "The short term goal is a microsat flight test." | judge whether the event happened (stance) |
| Conference-paper title and author block | "...Sounding Rocket One Flight Test Jake A." | skip front matter by layout, not report number |
| Relevant vs operational flight | suborbital sounding rocket counted as operational | meaning, not keywords |

All four point to an entailment judge (catalogue `deberta-v3-base-zeroshot-v2.0-c`) asking "does this
sentence report a completed test of the target?", which belongs in the criterion judge (Task 11).

## Judge notes (2026-11-02)

- **Conservative thresholds lose.** On the odd USGS cases a single threshold of 0.9 gives B 0.47 and 0.5 gives
  0.52; per-criterion thresholds give 0.675. B weights a missed `met` twice, and a quote that is really on the
  page cannot score below 0 in Part C.
- **The judge does not improve the TRL yet.** On the 49 odd USGS cases, rules using its scores reach 0.796 in
  sample but 0.746 under cross-validation, below the type default's 0.786. So the default stays.
- **Worst cases, 2 threads:** 3 PDFs at the 300-page limit 88 s, largest PDF (USGS-SDG-017) 73 s, scanned report
  (USGS-SDG-030) 69 s, against the 180 s limit. Peak worker memory about 1.2 GB. No GPU tested.
- **Draft labels:** `data/public_criteria_labels.json` is unreviewed and written from candidate sentences, so
  treat the USGS B figures as a rough guide. Their gold pages can miss good pages, which understates B.
