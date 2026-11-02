# Team Cache Kita: TRL assessment module

APCTT Hackathon 2026, Stage 1. Package `cache-kita-trl`, entry point
`participant_module.adapter:AssessmentModule`, CPU only, MIT licensed.

## What it does

For each case the module reads the text of every PDF page, splits it into sentences and assigns
a Technology Readiness Level (TRL 1-9), or abstains with a reason.

1. **Page reading** (`adapter.py`): plain text per page with pypdfium2, so every page number
   cited is the real page number in the PDF.
2. **TRL decision** (`trl.py`): depends on the assessment target's type.
   - `technology` and `system` (models, data products and arrangements deployed in the field) start
     from a default: TRL 6 and TRL 7, set from the organizer's reference estimates for the public
     sample cases. This is not yet a judgement of the individual report. The module abstains when no
     text can be read or a concept-level system is built from heritage parts.
   - `component` and `subsystem` use keyword cues per level, based on the NASA NPR 7123.1 and EU
     Horizon TRL definitions (team cheat-sheet). A sentence counts as evidence only when it reports
     what was built or tested. Sentences that just claim a TRL ("reached TRL 6"), describe plans
     ("will be tested") or report failures are ignored. The module takes the highest level with real
     evidence and abstains when there is none.
3. **Criteria**: every checklist criterion is reported as `insufficient evidence` with a
   `missing_evidence` note until the criterion judge is added. A wrong `met` costs both the
   evidence score and the quote review.
4. **Output and time** (`output.py`, `budget.py`): every result is built in one place and checked
   against the data contract locally. A time guard returns before the 3-minute limit, and errors
   become a clean failed result with an `error_code`.

## How it was built

- Rule-based, standard library plus pypdfium2 from the common base environment. No models, no
  training, no data shipped (`declaration.json`: `no_team_training`).
- Developed and checked on 16 hand-labelled NASA NTRS reports, then scored once on 5 held-out
  reports that were labelled before the module ever ran on them. The kit's USGS public sample cases
  set the TRL defaults on the odd-numbered cases and were checked on the even-numbered ones. All sources, dates, licences and label origins are listed in
  `declaration.json`.
- Results per version are logged in the team repository (`team/EVAL_LOG.md`), produced with
  `team/regress.py`.
