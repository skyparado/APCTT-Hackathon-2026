# How to run the kit end to end (Task 3)

One page for the team. Everything runs from the kit's top-level directory, **inside WSL2
(Ubuntu)** — native Windows is not supported. Clone into `~/`, not `/mnt/c` (Task 2).

## One-time setup

1. **Server env** (runs the kit, not our module):
   ```bash
   uv venv --python 3.12 .venv
   uv pip install --python .venv/bin/python -r requirements-dev.lock
   uv pip install --python .venv/bin/python --no-deps -e .
   ```
2. **Base env** (where *our* module actually runs — same for every team):
   ```bash
   python3 tools/make_env.py --base-dir ../apctt-env
   python3 tools/make_env.py --check --base-dir ../apctt-env   # must pass on every laptop
   ```
   Put the Python path it prints into `worker.python` in your local config.

## Point the server at our module

Copy `config/dev.json` to `config/my.local.json` (the `*.local.json` name is ignored by git /
the bundler) and set:

```json
"module": {
  "package_id": "cache-kita-trl",
  "entrypoint": "participant_module.adapter:AssessmentModule",
  "module_root": "/absolute/path/to/APCTT-Hackathon-2026",
  "package_root": "/absolute/path/to/APCTT-Hackathon-2026/participant_module",
  "asset_root": "/absolute/path/to/APCTT-Hackathon-2026/assets",
  "example_only": false,
  "settings": {}
},
"worker": { "python": "/absolute/path/to/apctt-env/bin/python", "extra_env": {} }
```

`module_root` is the folder that **contains** `participant_module/`. Our skeleton module
(`participant_module/adapter.py`) always abstains and is contract-valid, so it is a safe
default to run against.

## Run the demo case

```bash
# terminal 1 — start the server
.venv/bin/python -m apctt_server --profile dev --config config/my.local.json

# terminal 2 — confirm it's up and we're loaded
curl -s http://127.0.0.1:8000/health/ready        # {"ready":true,...}
curl -s http://127.0.0.1:8000/v1/package          # package_id = ours, verification_status = verified

# submit the example case, then poll the Location it returns
curl -s -X POST http://127.0.0.1:8000/v1/assessments \
     -H 'Content-Type: application/json' --data @docs/EXAMPLE_REQUEST.json -D -
curl -s http://127.0.0.1:8000/v1/assessments/<assessment_id>   # repeat until job_status: finished
```

**A good run** shows `job_status: "finished"` and `result_origin: "module"` (the server kept our
output). `result_origin: "supervisor"` means the server **replaced** our output with a failure —
see below. Use a **new `request_id`** after any code change, or you get `409 REQUEST_ID_CONFLICT`
(a request_id is bound to the case + config + package hash).

## Regression run over every labelled case (Task 16)

With the server running on our module:

```bash
~/apctt-env/bin/python data/build_cases.py              # builds request.json, checks every quote is on its page
~/apctt-env/bin/python team/regress.py --save run.json  # A (TRL), B (criteria), quote validity, timings
```

Run it after every change and compare `run.json` files. `team/eval_trl.py` scores the TRL logic alone on
the labels' gold quotes (no server), which is an upper bound, not the real score.

## Verify the module without the server (fast loop)

```bash
python -I team/verify_module.py   # cross-checks our output against the kit's own validate_result
python -I team/test_module.py     # stdlib unit tests for the output builder + time guard
```
Both pass with 0 issues: the module is checked against `validate_result` (the same rules the
server uses) on the DEMO checklist, a checklist with different IDs, and a builder-produced
`completed` result. Always finish with a real server run — a direct call does not reproduce the
time limit or process isolation.

### Module layout (`participant_module/`)

| File | Role |
|---|---|
| `adapter.py` | `AssessmentModule` (load/assess/reset_case/close). Currently abstains; the real pipeline (Tasks 10-13) slots into `_assess_case`. |
| `output.py` | Builds the result with exactly the allowed fields and enforces the contract locally (Task 14). Build every result through here. |
| `budget.py` | `TimeGuard` — watch `remaining_ms()` and abstain before the 180 s TIMEOUT (Task 15). |

Everything in `participant_module/` is **stdlib-only**: at the event it runs in the common base
env, where the kit's `apctt_contracts` is not importable. `apctt_contracts.validate_result` is a
**dev-only** cross-check, used from `team/verify_module.py`.

## Where to look when something breaks

Per job: `server_data/jobs/<assessment_id>/` → `stdout.log`, `stderr.log` (tracebacks here),
`raw_output.bin` (our exact result bytes). The HTTP response's `diagnostics` carries
`output_issues`, `warning_codes` and `timings_ms`.

## What makes a case fail (`result_origin: "supervisor"`)

A **failed** case is one where the server did **not** return our result. `result.error_code` says why:

| `error_code` | What happened | How we trigger it by accident | Fix |
|---|---|---|---|
| **`INVALID_OUTPUT`** | Our result broke the result contract, wasn't strict JSON, or `assess` returned a non-mapping (NaN, non-string keys, a custom object). | Not copying `schema_version` / `case_id` / `checklist_version` / `assessment_target` **exactly**; a checklist criterion missing from `criterion_status` or `evidence_reference`; `met` with no evidence; `insufficient evidence` with no `missing_evidence`; a page beyond the PDF; `null` for an optional field; an extra field. | Read `diagnostics.output_issues` (`path` + `rule`); rules in DATA_CONTRACT §4.2. Our output builder (Task 14) must enforce these before returning. |
| **`TIMEOUT`** | The case exceeded `deadline_ms` = **180 s**. This covers interpreter start-up, imports, `load`, `assess`, cleanup and exit — not just `assess`. A result already written is discarded. | Slow model loading on every case (cold process per case), heavy top-level imports, no early return on huge PDFs. | Load once in `load()`; watch `context.remaining_ms()` and return an abstained/failed result before the limit (Task 15). |
| **`OUT_OF_MEMORY`** | PyTorch raised `torch.cuda.OutOfMemoryError`, or we set `apctt_error_code="OUT_OF_MEMORY"`. A process the OS kills without such an exception shows as `WORKER_CRASH` instead. | Loading several models at once, long inputs, big batches (ref GPU budget ~7.0 GiB). On CPU, excessive RAM. | Keep memory low; smaller batches; release between stages (Task 15). |
| `MODULE_ERROR` | Our code raised in `load` or `assess`. | Any uncaught exception. | Fix it; our `assess` wraps its body and returns a clean `failed` result instead of raising. |
| `CLEANUP_ERROR` | `reset_case()` or `close()` raised (even though a result was written). | Releasing a resource that isn't there. | Make both never raise. |
| `WORKER_CRASH` / `WORKER_PROTOCOL_ERROR` | Worker died abnormally, called `sys.exit`/`os._exit`, or wrote no `result.json`. | Calling `sys.exit`, spawning daemons, writing `result.json` ourselves. | Just `return` the result from `assess`; never touch `result.json`. |

Note: a result **we** return with `assessment_status: "failed"` and our own `error_code` is a
*valid* result (`result_origin: "module"`) — that is not a server failure, it is us reporting we
could not assess the case.

## Request-level rejections (before the job even runs)

These come back on the `POST` as `4xx`, not as a job: `REQUEST_VALIDATION_ERROR` (422),
`VERSION_MISMATCH` (422, wrong `schema_version`/`checklist_version`), `UNSUPPORTED_INPUT_PROFILE`
(422), `REQUEST_TOO_LARGE` (413), `409 REQUEST_ID_CONFLICT`, `503 BUSY` (another case running —
retry). Full table: TROUBLESHOOTING §2.

## Reference

QUICKSTART, MODULE_GUIDE, DATA_CONTRACT (§4.2 result rules), TROUBLESHOOTING (§3 failure codes),
SUBMISSION, MODEL_CATALOG — all under `docs/participant/`.
