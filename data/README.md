# Labelled test cases (Task 8)

Our mini evaluation set. Each case is one folder that the regression script (Task 16) can send
straight to the kit server and score against our labels.

```
data/
  build_cases.py          check every case, build its request.json
  sources.csv             where every document came from (feeds declaration.json, Task 20)
  cases/
    EX-001/               synthetic worked example: copy this folder to start a new case
      case.json           the case, in the kit's format (DATA_CONTRACT 1.2), PDFs by file name
      labels.json         our answer: TRL, evidence quotes, criterion statuses
      D001.pdf            the report(s)
      request.json        generated, git-ignored: the exact POST /v1/assessments body
```

## Add a case

1. Copy `cases/EX-001/` to `cases/<NEW-ID>/` (folder name = `case_id`) and drop in the PDFs.
2. Edit `case.json`: target, `type` (`component` / `subsystem` / `system` / `technology`),
   intended application and environment, one entry per PDF. **No labels here**: the server rejects
   unknown fields such as `trlCurrent`.
3. Write `labels.json` using [team/TRL_CHEATSHEET.md](../team/TRL_CHEATSHEET.md).
4. Add one row per document to `sources.csv`.
5. Run the builder (from the repo root):
   ```
   python -I data/build_cases.py
   ```
   Run it inside WSL too: there pypdfium2 is available, so it also checks every quote is really
   on its page. On plain Windows those two checks are skipped with a note.

## labels.json

| Field | Meaning |
|---|---|
| `assessment_status` | `completed` (a TRL is determinable) or `abstained`. Abstained cases are useful: a correct abstention scores full marks. |
| `trl` | Integer 1-9 when completed, `null` when abstained. |
| `abstention_reason` | `null`, or one of `insufficient evidence`, `conflicting evidence`, `ambiguous scope`, `out of scope`. |
| `trl_rationale` | Why this level and not the one above. Name the trap you avoided. |
| `evidence[]` | Best sentences first: `trl_level`, `document_id`, `page`, `quote` (copied exactly from the PDF), `note`. |
| `criteria` | Optional until the official checklist is out: `criterion_id -> {status, pages}`. Every `met` needs gold pages. |
| `labelled_by`, `labelled_on`, `label_origin` | Who, when (YYYY-MM-DD), and where the TRL came from. |

## Labelling rules

- Quote what was **built, tested, where, with what result**. A sentence that only states a TRL
  is never evidence; the builder rejects it.
- Copy quotes exactly from one page; never paraphrase.
- From NASA TechPort use only the **current** TRL, and read the actual reports, not the summary
  (SUBMISSION 2). Do not copy a project-level TRL onto a component.
- Mix levels (aim for low, mid and high TRLs) and include 1-2 cases where no TRL is determinable.
- When the official checklist is published, update `checklist_version` in every `case.json` and
  fill `criteria` with the official IDs.
