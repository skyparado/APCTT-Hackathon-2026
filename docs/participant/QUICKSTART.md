# Quickstart — first run in about 15 minutes

kit 0.4.0 | API `apctt-api-v0.2-draft`

By the end of this page you will have installed the server, sent the example case, read a finished
result, opened the offline API documentation and run the conformance tests. Your own module comes
next, in [MODULE_GUIDE.md](MODULE_GUIDE.md).

All commands run from the kit's top-level directory. Outputs below were produced by this kit; your
IDs, hashes and times will differ.

## 1. What you need

- Linux or WSL2 (macOS also works for local development). Native Windows is not supported.
- Python 3.12 and uv (or `pip` with `--require-hashes`).
- `curl` for the examples below (any HTTP client works).
- Port 8000 free on `127.0.0.1` (change `bind_port` in a local config if it is not).

## 2. Install and start the server

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-dev.lock   # server + test tools
uv pip install --python .venv/bin/python --no-deps -e .            # the kit's own packages
```

`requirements-server.lock` contains only the server's runtime dependencies (FastAPI, Pydantic,
Uvicorn, pypdf for page counting, and their dependencies). `requirements-dev.lock` adds pytest, httpx, ruff and mypy. Both
pin exact versions with hashes. Your module does not run in this environment: it runs in the
common base environment, the same for every team, built with `tools/make_env.py` (README step 5,
[MODULE_GUIDE.md](MODULE_GUIDE.md) §7).

Start the server:

```bash
.venv/bin/python -m apctt_server --profile dev --config config/dev.json
```

```text
INFO:     Started server process [62116]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

At start-up the server opens its job store in `server_data/`, computes a hash of the example
package and checks the configuration. If a check fails it exits with
`APCTT_START_REFUSED <CODE>` (see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) §6).

Check it from a second terminal:

```bash
curl -s http://127.0.0.1:8000/health/live
# {"live":true,"api_version":"apctt-api-v0.2-draft"}
curl -s http://127.0.0.1:8000/health/ready
# {"ready":true,"reason_code":"READY","loading_policy":"cold_per_case",
#  "active_assessment_id":null,"compute_status":{"device":"cpu","require_cuda":false,"status":"NOT_REQUIRED"}}
```

`/health/ready` answers 200 only when a new case can be accepted right now. While a case is running
it answers 503 with `reason_code: "BUSY"`.

## 3. Send the example case

`docs/EXAMPLE_REQUEST.json` is a complete synthetic request:
`{"request_id": "DEMO-REQ-001", "case": {…}}` with one PDF document, `docs/EXAMPLE_REPORT.pdf`
(2 pages), embedded as base64 with its SHA-256. `tools/make_request.py` builds such a file from your own
PDFs (README, step 7).

```bash
curl -s -X POST http://127.0.0.1:8000/v1/assessments \
     -H 'Content-Type: application/json' --data @docs/EXAMPLE_REQUEST.json -D -
```

```text
HTTP/1.1 202 Accepted
location: /v1/assessments/9b69849dd5ff46148b3622b9597d2be3
content-type: application/json
```

```json
{
  "assessment_id": "9b69849dd5ff46148b3622b9597d2be3",
  "request_id": "DEMO-REQ-001",
  "job_status": "queued",
  "result_origin": null,
  "result": null,
  "meta": {
    "trace_id": "ca0a6d1e290d4381bee99a915a572f08",
    "api_version": "apctt-api-v0.2-draft",
    "schema_version": "apctt-pdf-example-v1",
    "package_id": "participant-example-cpu",
    "input_sha256": "bef3cc06729651a5279a98c8e5a5a5a17df67292476b79aa0e7bb23eb661b010",
    "config_sha256": "b54452547b816f95e2a4d414aa771b0ace65fced1d996584ab9cc221c9d1f202",
    "verified_package_sha256": "fc0df13a9da89a4b49d42eba8d2d771e0e066a9f489992a448f11c276326accf",
    "accepted_at": "2026-09-29T15:48:23.621Z",
    "started_at": null,
    "finished_at": null
  },
  "diagnostics": {
    "profile": "dev",
    "phase": "queued",
    "accepted_trace_id": "ca0a6d1e290d4381bee99a915a572f08",
    "loading_policy": "cold_per_case"
  }
}
```

`202 Accepted` means the job was stored; the case runs in the background. Closing your client does
not cancel it. Sending the same body again returns the same job (same `Location`) instead of
running it twice.

## 4. Poll for the result

```bash
curl -s http://127.0.0.1:8000/v1/assessments/9b69849dd5ff46148b3622b9597d2be3
```

Repeat until `job_status` is `finished` (`queued` → `running` → `finished`). The example module
finishes in well under a second. The finished job, shortened:

```json
{
  "job_status": "finished",
  "result_origin": "module",
  "result": {
    "schema_version": "apctt-pdf-example-v1",
    "checklist_version": "DEMO-CHECKLIST-NOT-OFFICIAL",
    "case_id": "DEMO-001",
    "assessment_target": {
      "target_id": "T001",
      "type": "component",
      "description": "Synthetic sensor fixture; not a validated technology"
    },
    "assessment_status": "abstained",
    "predicted_trl": null,
    "criterion_status": {"DEMO-C01": "met", "DEMO-C02": "insufficient evidence"},
    "evidence_reference": {
      "DEMO-C01": [
        {"document_id": "D001", "page": 1, "supporting_span": "tested"}
      ],
      "DEMO-C02": []
    },
    "missing_evidence": {
      "DEMO-C02": "DEMO rule: no page contains a configured phrase for this criterion."
    },
    "abstention_reason": "insufficient evidence",
    "error_code": null,
    "criterion_rationale": {"DEMO-C01": "DEMO rule: a configured phrase appears in D001 page 1."}
  },
  "diagnostics": {
    "phase": "finished",
    "timings_ms": {"load": 0.788, "assess": 40.085, "cleanup": 0.002, "total": 94.342},
    "timing_sources": {
      "load": "worker_observed",
      "assess": "worker_observed",
      "cleanup": "worker_observed",
      "total": "supervisor"
    },
    "exit_code": 0,
    "timed_out": false,
    "cleanup_confirmed": true,
    "raw_output_bytes": 773,
    "warning_codes": []
  }
}
```

## 5. Read the result

| Field | Meaning in this example |
|---|---|
| `result_origin: "module"` | The module's output passed every contract check and is returned as the module produced it. `"supervisor"` would mean the server replaced it with a failure result. |
| `assessment_status: "abstained"` | The example module gives a TRL only when every DEMO criterion is met. |
| `criterion_status` | One value per checklist criterion: `met`, `not met` or `insufficient evidence`. |
| `evidence_reference.DEMO-C01` | Where the evidence is: document `D001`, page 1, and the supporting words `"tested"`. |
| `missing_evidence.DEMO-C02` | Why `DEMO-C02` is `insufficient evidence`; required for that status. |
| `criterion_rationale` | Optional explanation per criterion. |
| `diagnostics.timings_ms` | `load`/`assess`/`cleanup` measured inside the worker; `total` measured by the server from before the worker started until its processes were gone. |

The result is stored as canonical JSON, so keys come back sorted; values are unchanged.
Every field and rule is in [DATA_CONTRACT.md](DATA_CONTRACT.md); every diagnostics field is in
[API_REFERENCE.md](API_REFERENCE.md) §6.

**How the example module decides.** It reads the text of every PDF page with `pypdf` and searches
it for the phrases configured in `config/dev.json` → `module.settings.criteria_phrases`
(case-insensitive). A match makes the criterion `met` and cites that document and page with the
matched words. No match makes it `insufficient evidence`. If all criteria are met it returns
`completed` with `predicted_trl` = `completed_trl` (4); otherwise `abstained`. Add a PDF whose text
contains "acceptance criteria were met" and the result becomes `completed`. A real module chooses
its own way to read PDFs; this one is a format example.

## 6. Other things to try now

- **Swagger UI:** open `http://127.0.0.1:8000/docs`. It works offline; "Try it out" on
  `POST /v1/assessments` sends a real request.
- **Package and configuration identity:** `curl -s http://127.0.0.1:8000/v1/package` shows the
  profile, versions, `verified_package_sha256` and the compute settings.
- **A validation error:** change the document's `sha256` to 64 zeros in a copy of the request and
  submit it → `422 REQUEST_VALIDATION_ERROR` with `path: "case.documents[0].sha256"` and
  `rule: "document_sha256_match"`.
- **A conflict:** submit the same `request_id` with a changed `title` → `409 REQUEST_ID_CONFLICT`.
- **Conformance tests:** run

  ```bash
  .venv/bin/python -m pytest
  ```

  They take about a minute. They start their own server and worker processes on free ports in
  temporary directories, so your running server is not affected. They check admission,
  duplicates, time-outs, crash handling, restart recovery, leak prevention, path handling and the
  result rules. All must pass on your machine.

## 7. Stop and reset

Stop the server with `Ctrl+C`. If a case is still running, its worker is terminated and the job is
recorded as `failed` with `error_code: "SERVER_RESTARTED"` at the next start; it is not re-run.

Everything the server stored is in `server_data/`:

```text
server_data/
├── jobs.sqlite3                 job state, results, hashes
├── events.jsonl                 event log (IDs, codes and timings only)
├── server.lock                  prevents two servers using the same directory
└── jobs/<assessment_id>/
    ├── raw_output.bin           your module's result bytes exactly as written
    ├── stdout.log               first 1 MiB of your module's standard output
    └── stderr.log               first 1 MiB of standard error (tracebacks appear here)
```

`worker_tmp/` holds each case's private scratch directory while it runs and is emptied afterwards.
To start from a clean state, stop the server and delete `server_data/` and `worker_tmp/`.
Results are never deleted automatically.

## 8. Next

Read the challenge in full: [PROBLEM_DESCRIPTION.md](PROBLEM_DESCRIPTION.md). Then build the base
environment, get the catalogue models you need and write your own module: README steps 5–7 and
[MODULE_GUIDE.md](MODULE_GUIDE.md).
