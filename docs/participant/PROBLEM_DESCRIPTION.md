# Problem description — TRL assessment of technical reports

kit 0.4.0 | event procedure of 2026-10-10 (decisions D55–D67)

**Status.** This page describes the whole challenge: the task, the fixed environment and the model
catalogue, what you submit, how your package is run and how it is scored. The organizer decided
the procedure on 2026-10-10. Values that the builder of this kit chose as defaults, and
interpretations of the organizer's decisions, are marked **[to be confirmed]** and are listed again
in §18. The official announcements (dates, the official checklist, the machine specification) and
the official participation terms prevail over this page. Read this page first; the other guides
explain how to do each step.

## 1. Background

APCTT (the Asian and Pacific Centre for Transfer of Technology) supports the transfer of
technologies between organisations. Before a technology is transferred, funded or deployed,
someone has to judge how mature it is. The common yardstick is the **Technology Readiness Level
(TRL)**, a scale from 1 (basic principles observed) to 9 (actual system proven in operational
use). A TRL is assigned by reading the evidence, usually technical reports: what was built, how it
was tested, in which environment, and whether the results met the stated criteria.

Doing this by hand is slow, and different assessors read the same report differently. This
hackathon asks for a system that reads the technical reports about one technology and proposes a
TRL **together with the evidence for it**: for each criterion of a checklist, whether it is met and
on which page of which report the support is. An assessor can then check the judgement page by
page instead of rereading everything.

The competition has two stages:

- **Stage 1**: you build an *Assessment Package*, a Python module that assesses cases. The
  organizer runs it on hidden cases and scores the results automatically and with expert review.
- **Stage 2**: the teams that advance build a web system around their frozen Stage 1 package, for
  an assessor to use, and demonstrate it offline on the event computers.

## 2. The task

Each **case** is one assessment target (a component, subsystem, system or technology) described by
one or more PDF reports. Your module receives the case and returns one **result**:

1. for every criterion of the checklist: `met`, `not met` or `insufficient evidence`;
2. for every `met` criterion: the evidence, as (document, page) references, each with an optional
   short quotation (`supporting_span`) from that page;
3. either a TRL from 1 to 9 (`completed`), or an abstention with a reason (`abstained`: the
   evidence does not allow a TRL), or a failure (`failed`).

How you read the PDFs (text extraction, layout analysis, OCR, retrieval, a language model, rules or
a combination) is your choice, and it is what you compete on. Training a model is allowed but not
required; a rules-based or retrieval-based module is equally welcome.

## 3. Input: a case

A case reaches your module as a mapping (the server has already checked it):

| Field | Meaning |
|---|---|
| `case_id` | Neutral identifier of the case. |
| `assessment_target` | `target_id`, `type` (`component`, `subsystem`, `system` or `technology`) and `description` of what is assessed. |
| `intended_application`, `intended_environment` | What the technology is meant for and where it must work. A TRL is always relative to these. |
| `title`, `assessment_as_of` | Title of the case, and the date of the assessment (or `null`). |
| `documents` | One or more PDFs, in their original order. Each has `document_id`, `title`, `document_date`, `language` (`en`), `page_count` (counted by the server) and `path` (a read-only copy of the PDF). |
| `schema_version`, `checklist_version`, `input_profile` | Versions you copy into your result. |

Default limits: up to 20 PDFs per case, 20 MiB per PDF, 2,000 pages per case. The official limits
are announced with the official checklist; the 3-minute time limit per case (§12) is fixed. The
reports are in English. The organizer removes explicit TRL labels from the case fields, but the
text of a report may still state a TRL: see the evidence rule in §13.4. Every field:
[DATA_CONTRACT.md](DATA_CONTRACT.md) §1.

## 4. Output: the result

Your module returns a JSON object with exactly these fields:

| Field | Rule |
|---|---|
| `schema_version`, `checklist_version`, `case_id`, `assessment_target` | Copied from the case and the checklist. |
| `assessment_status` | `completed`, `abstained` or `failed`. |
| `predicted_trl` | Integer 1–9 when `completed`, otherwise `null`. |
| `criterion_status` | Every checklist criterion → `met`, `not met` or `insufficient evidence`. |
| `evidence_reference` | Every checklist criterion → a list of `{document_id, page, supporting_span?}`. A `met` criterion needs at least one item; the page must exist in that PDF. |
| `missing_evidence` | For every `insufficient evidence` criterion, a short explanation of what is missing. |
| `abstention_reason` | When `abstained`: `insufficient evidence`, `conflicting evidence`, `ambiguous scope` or `out of scope`. |
| `error_code` | When `failed`: your own short code. |
| optional | `confidence` (0–1), `uncertainty` (a TRL interval), `trl_rationale`, `criterion_rationale`. |

The server checks the structure and consistency of every result (for example, a `met` criterion
without evidence, a page beyond the end of the PDF, an unknown field). A result that breaks a rule
is not kept: the case is recorded as `failed` (`INVALID_OUTPUT`), and a failed case scores 0
(§13). The kit's server applies exactly the same checks, so you see every problem before you
submit. The server does not check whether a quotation really appears on the cited page (PDF text
extraction differs between tools); the experts do (§13.4). Every field, every rule, and valid and
invalid examples: [DATA_CONTRACT.md](DATA_CONTRACT.md) §2–4.

## 5. The checklist

The checklist is the list of criteria your module judges, each with a `criterion_id` and a
`description`. The **official checklist** is announced by the organizer and used for all three
submissions, the hidden evaluation and Stage 2. The kit contains only a DEMO checklist with two
criteria (`DEMO-CHECKLIST-NOT-OFFICIAL`), so that you can build and test the interface before the
official one is out.

Your module receives the checklist in `load()` and must take the criterion IDs from there: never
hard-code the DEMO IDs. Test your module with a changed copy of the DEMO checklist
([CONFIGURATION.md](CONFIGURATION.md) §4). The checklist never contains answers.

## 6. Timeline

All dates are announced by the organizer **(to be announced)**. The order is fixed:

| # | Step | What happens |
|---|---|---|
| 1 | Registration | Teams register and accept the participation terms. The machine specification is announced after registration closes. |
| 2 | Kit, base and catalogue published | This kit, the common base environment (§7) and the model catalogue (§8) are published and frozen; the official checklist and the public sample cases follow. Before publication the organizer measures every catalogue model on the reference GPU (§8.2). |
| 3 | **Submission 1 — check** | The organizer runs your package on the public sample cases and returns pass/fail and diagnostics. Not scored. |
| 4 | **Submission 2 — interim check** | The organizer runs your package on a separate interim case set and returns diagnostics and the automatic scores A and B, privately. Not counted. |
| 5 | **Submission 3 — final** | Your final package. It is run once on the frozen hidden cases. **Only submission 3 is scored.** |
| 6 | Expert review | Experts, recruited after the final submission, label the hidden cases, judge sampled evidence and review frequently cited pages (§13). |
| 7 | Results and appeals | Provisional results, a 48-hour appeal window (§13.7), the finalist run on 10 more hidden cases, then the Stage 1 results. |
| 8 | Stage 2 hackathon and demonstration | Advancing teams merge their web system with their frozen package on the event computers and demonstrate it offline (§14). |

Between submissions you may change your code, your rules and which catalogue models you use; each
submission is checked in full, and only what you send as submission 3 is scored. Interpretations
**[to be confirmed]**: submissions 1 and 2 are optional (missing them only loses that feedback);
each submission round takes one upload per team; the organizer announces when the results of
submissions 1 and 2 come back.

## 7. The fixed environment

You do not submit an environment, and there is **no environment proposal**. The organizer runs
every package in one fixed environment that it builds itself, the same for every team, so the
evaluation can run every team on 5 machines without installing anything from a submission.

### 7.1 The common base environment

One **base environment** is the same for every team: Linux x86_64, CPython 3.12, the PyTorch
closure of torch 2.11.0+cu128 (with its CUDA 12.8 libraries) and a set of common, licence-allowed
packages. Its identifier is `base_id` `apctt-base-9e7fe1324bb6`; the exact versions and hashes are
in `requirements-base.lock` (94 packages), `constraints-base.txt` and
`contracts/base-environment.json`. Main packages:

| Area | Packages in the base |
|---|---|
| Numerics, classical ML | numpy 2.5.3, scipy 1.18.1, scikit-learn 1.9.1, pandas 3.0.6 |
| Transformer models | torch 2.11.0, transformers 5.19.0, tokenizers 0.23.3, safetensors 0.8.0, huggingface-hub 2.2.0, sentence-transformers 5.7.0, accelerate 1.15.0, peft 0.21.2, bitsandbytes 0.50.2 |
| PDF text, layout, OCR | pypdf 6.19.0, pdfplumber 0.11.10, pdfminer.six 20260107, pypdfium2 5.14.0, onnxruntime 1.31.0, rapidocr-onnxruntime 1.4.4, opencv-python-headless 5.0.0.93, pillow 12.3.0 |
| Stage 2 web systems | fastapi 0.141.1, uvicorn 0.54.0, jinja2 3.1.6, python-multipart 0.0.32, httpx 0.28.1, pydantic 2.13.5 |

The rules of the base:

- **One base, frozen.** The base is frozen when the kit is published. It changes only by an
  organizer announcement that applies to every team (with a new `base_id`); there are no per-team
  packages and no requests for packages.
- **Your module runs in the base's own Python.** `tools/make_env.py` builds the same base on your
  computer and prints that interpreter; you put it into `worker.python` of your local configuration
  (README steps 5 and 6). Never install anything into the base by hand: the organizer's machines
  would not have it.
- **Use the base versions.** A package in your submission with the import name of a base package
  (for example a copied `transformers/`) is refused. Your own pure-Python code, and third-party
  pure-Python modules you copy into `participant_module/` with their licences (decision D66, §15),
  are part of your package; compiled extensions are refused.
- **Nothing outside the base.** Programs outside Python (for example a system OCR engine) are not
  provided; use packages of the base (for example `rapidocr-onnxruntime` or `pypdfium2`).

### 7.2 CPU only is fully allowed; a GPU is optional

A module that uses only the CPU (`compute.device` `cpu` in `submission.json`) is fully allowed and
is scored by exactly the same rules and time limit as a GPU module (decision D57). The base
contains the CUDA build of PyTorch, which runs on the CPU as well. With `cuda:0`, your module runs
on the machine's NVIDIA GPU and must fit its memory. The **reference GPU** is the GPU of the event
machine: an **NVIDIA RTX 3070 Laptop GPU with 8 GB VRAM** (8 GiB, on Ubuntu 24.04; decisions D40 and
D67). The machine specification is announced after registration; the plan assumes 5 machines of
this type **[to be confirmed]**. For development without an NVIDIA GPU (macOS, or Linux and WSL2
without one), `tools/make_env.py` builds a CPU development base with the same package versions.

### 7.3 Offline execution

The evaluation and the Stage 2 demonstration run **without network access** (decision D46).
Nothing may be downloaded while a case runs. Your code and your own weights are in your package,
public models are in the read-only model store (§8), and packages come from the base. Set
`HF_HUB_OFFLINE=1` in your own code before you import Hugging Face libraries, and load models with
`local_files_only=True` ([MODULE_GUIDE.md](MODULE_GUIDE.md) §7).

## 8. The model catalogue

### 8.1 What is provided

The organizer selected public models that fit on the 8 GB reference GPU and provides them: the
**model catalogue** `contracts/model-catalog.json`, listed with sizes, VRAM estimates and CPU
options in [MODEL_CATALOG.md](MODEL_CATALOG.md) (`python tools/get_models.py --list` prints the
same list). It is the organizer's recommended public model set for the reference GPU, RTX 3070
Laptop GPU with 8 GB VRAM (decisions D64 and D67). The catalogue has 23 models, all Apache-2.0 or
MIT, each at a pinned revision:

| Kind | Models |
|---|---|
| Language models (bf16) | 6, from 0.5B to 2.5B parameters; the two smallest are CPU-friendly |
| Language models (4-bit, GPU only) | 5 options from 3B to 8B parameters, conditional on the GPU measurement (§8.3) |
| Embedding models | 5, most of them CPU-friendly |
| Rerankers | 3 |
| Zero-shot entailment (NLI) | 2 |
| Encoder backbones for team-trained classifiers | 2 |

On every evaluation machine the organizer puts every catalogue model into a **read-only model
store**, laid out as `<store>/<org>/<name>/<revision>/`; your module finds the store in the
environment variable `APCTT_MODEL_STORE`. For development, `python tools/get_models.py ID --store
DIR` downloads the same files into the same layout, and `python tools/get_models.py --snippet ID`
prints the loading code.

### 8.2 The 8 GB budget: estimates and measurement

Every catalogue entry fits a budget of **at most 7.0 GiB peak** on the 8 GiB card: weights + KV
cache or activations + 1.0 GiB of overhead for the CUDA context. Language models are budgeted at
8,192 tokens of context (batch 1), encoders at a batch of 32 × 512 tokens. **The VRAM figures are
estimates** until the organizer measures them: before the kit is published the organizer runs
`tools/hq/check_models_gpu.py` on the RTX 3070 Laptop GPU and removes any entry that does not load
within the budget. Your own use (longer inputs, larger batches, several models at once) is your
responsibility: an out-of-memory error fails the case (`OUT_OF_MEMORY`).

### 8.3 4-bit options

Five language models are offered in 4 bits (bitsandbytes nf4, which is in the base): they load the
publisher's bf16 weights and quantise them on the GPU while loading. They are marked
`"measured": false` and are **conditional on the GPU measurement**: before the kit is published the
organizer runs `tools/hq/check_models_gpu.py` on the RTX 3070 Laptop GPU and removes any 4-bit
entry that does not load within the budget (peak at most 7.0 GiB, and a load well inside the
3-minute limit of a case). They need a CUDA GPU; none of them runs on the CPU. **Cold-load
warning:** the 7–8B entries read 14.50–16.35 GB of weights from disk and quantise them in every case,
because every case starts a new process (§12); time your load before you depend on them.

### 8.4 What you may use

- **Catalogue models**, named in `submission.json` `models[]` by `catalog_id`. Their weights are
  never in your zip: the organizer provides them. The catalogue records the size and sha256 of
  every catalogue weight file, and a file with those bytes is refused however it is named or
  declared (also as `"team_trained": true`).
- **Weights your team trained**, shipped in `assets/` and declared in `models[]` as
  `"team_trained": true` with their `path`. A fine-tune or adapter (for example LoRA) of a
  catalogue model is your own work: name its catalogue base in `base_model`.
- **Nothing else.** A public model outside the catalogue cannot be used, whatever its licence:
  it is not available offline at the event, and public model weights may not be shipped in a
  submission (interpretation **[to be confirmed]**). There are no exceptions. The kit's check
  refuses catalogue weights by their bytes and undeclared weight files over 50 MiB; an undeclared
  weight file under 50 MiB that looks like a public model is a licence review item, which the
  organizer decides after the submission (§9). The rule itself is the same for small files: a
  public model outside the catalogue may not be used at any size (see §16 for the consequences).

## 9. No advance approval

Nothing is approved in advance, for any team (decision D63). The rules are published, mechanical
and the same for every team:

- **Check yourself with the kit's tools.** `tools/make_env.py --check` (your environment is the
  base), `tools/get_models.py --check` (your model copies), `tools/make_submission.py` (packs your
  zip and checks it exactly as the organizer's intake does, including the licence checker
  `tools/check_licenses.py`).
- **Checks at submission.** Every submission is checked in full at intake with those rules.
  Passing submission 1 or 2 is feedback, never an approval of a later submission.
- **Review items are decided after the submission.** Licence items that the policy marks
  "review" (for example weak copyleft in copied code) are decided by the organizer after the
  submission; there are no advance rulings on your package. Questions about the rules in general
  are answered for all teams alike **[to be confirmed: how]**.
- **No exceptions.** The 2 GB size cap, the 3-minute limit per case (model loading included), the
  absence of network access and the frozen base apply to every team; there are no per-team
  resources, packages or models.

## 10. What you submit

### 10.1 The minimal bundle

You submit one zip, `<team>_submission.zip`, made by `tools/make_submission.py`. It contains **no
environment**: no packages, no virtual environment, no PyTorch or CUDA, no public model weights.

```text
<team>_submission.zip
├── participant_module/      your code and rules
│   ├── __init__.py
│   ├── adapter.py           entry point participant_module.adapter:AssessmentModule
│   ├── LICENSE              Apache-2.0 or MIT, full text
│   └── THIRD_PARTY_NOTICES.md
├── assets/                  only weights and rules your team trained or wrote (may be empty)
├── submission.json          team, package_id, package_version, base_id, declared_package_sha256,
│                            license, compute, settings, models
├── declaration.json         the data declaration
└── README.md                what your module does and how it was built
```

`submission.json` follows `contracts/submission.schema.json`: `base_id` is the kit's common base,
`compute.device` is `cpu` or `cuda:0`, `settings` is passed to `load()`, and `models[]` lists the
catalogue models you use (`catalog_id`) and your team-trained weights (`name`, `path`,
`"team_trained": true`, and `base_model` for a fine-tune or adapter). `declared_package_sha256` is
the hash of `participant_module/` and `assets/`, computed and written by `tools/make_submission.py`
with the same function the server uses; the organizer recomputes it, and it must equal the hash the
server reports while it runs your cases. Details: [SUBMISSION.md](SUBMISSION.md) §1.

### 10.2 What is refused

Anything other than the five entries above; symbolic links; compiled extensions and binaries
(`.so`, `.pyd`, `.dylib`, `.dll`, `.exe`), wheels, virtual environments, `site-packages`, installed
package metadata, `.git` and `node_modules` folders; copies of base packages; any file with the
bytes of a catalogue weight file (size and sha256 recorded in `contracts/model-catalog.json`),
whatever its name and even if declared as team-trained; weight files over 50 MiB that `models[]`
does not declare as team-trained; a `models[]` entry outside the catalogue, a catalogue model with
weights in the zip, or a `base_model` outside the catalogue; a `base_id`
other than the kit's base; a package hash that differs from the declared one; and anything the
licence checker refuses. Run the tool yourself: it refuses exactly what the organizer refuses.
Undeclared weight files under 50 MiB are not refused by the tool: the licence checker lists them as
review items, and the organizer decides them after the submission (§8.4).

### 10.3 Size

The zip may be at most **2 GB** (2,000,000,000 bytes), for every team. Catalogue models do not
count: they are in the model store.

## 11. Three submissions

### 11.1 What each submission returns

| | Submission 1 — check | Submission 2 — interim check | Submission 3 — final |
|---|---|---|---|
| Cases | The public sample cases | A separate interim case set, never reused in the final set | The frozen hidden set (and 10 more hidden cases for finalists) |
| You get back | PASS or FAIL, and per case: status, TRL, error code, the server's fixed failure sentence, output issues (path and rule), warning codes, timings | The same diagnostics, plus your automatic scores A and B and their total renormalised to 45:40, privately | A receipt: accepted or refused, the hashes of your zip and package, the base and the models |
| Scored | No | No (not counted, no public ranking) | **Yes: the only scored submission** |

PASS means that the intake accepted your zip and every case produced a contract-valid result
(`completed` or `abstained`). A refused zip comes back with the reasons. The interim feedback gives
totals only: no expected answers, no per-case scores, no case documents and no evidence text.
All three runs use the organizer's `evaluation` server profile, which shows no stack traces
**[to be confirmed]**. Default numbers of cases **[to be confirmed]**: 3 public sample cases, 5
interim cases, 10 final hidden cases, 10 more for the finalists.

### 11.2 Only submission 3 is scored

**A team without a submission 3 (final) is not scored and not ranked; no earlier submission is
used instead** (organizer decision of 2026-10-10). Submissions 1 and 2 are feedback only. A
submission 3 that the intake refuses counts as no final submission unless you submit a valid one
before the deadline **[to be confirmed]**. What to prepare and the data declaration:
[SUBMISSION.md](SUBMISSION.md).

## 12. How your package is run

- **Where.** The organizer copies your package, unchanged, into its pinned reference kit (the
  same server code as this kit) on one of **5 machines of the same specification**. Each machine
  runs one kit server and one case at a time. The base environment and the model store are
  read-only.
- **How.** Every case runs in a **new worker process**: `load` → `assess` → `reset_case` →
  `close`, then the process exits. Nothing is kept between cases, so every case pays its own
  interpreter start and model loading.
- **Time.** **3 minutes per case**, interpreter start and model loading included (decision D41).
  A case that is not finished is stopped and recorded as `failed` with `TIMEOUT`. Check
  `context.remaining_ms()` and return an `abstained` or `failed` result yourself before the limit.
- **First run is official.** Each case is run once and that run counts. A case is run a second
  time only when the failure was caused by the organizer's host (`SERVER_RESTARTED`,
  `INTERNAL_ERROR` from the server, or a host cause in the run log), once, and never after a
  `TIMEOUT`.
- **Offline and isolated.** No network. The worker sees only the environment variables listed in
  [MODULE_GUIDE.md](MODULE_GUIDE.md) §7 and `APCTT_MODEL_STORE`. The official checklist is used.

## 13. Scoring

### 13.1 Overview

The Stage 1 score of a team combines automatic scoring and expert review (decision D58), on the
results of its submission 3 only. The weights and constants of this section are defaults
**[to be confirmed]**:

```text
total = 0.45 × A  +  0.40 × B  +  0.15 × C        (each of A, B, C between 0 and 1)
```

| Part | Weight | What it measures | How |
|---|---|---|---|
| A — TRL decision | 45% | Whether your TRL (or abstention) matches the experts | automatic, per case |
| B — criterion evidence | 40% | Whether your criterion judgements and evidence pages agree with the experts | automatic, against expert labels |
| C — expert review | 15% | Whether your quoted evidence really supports the criterion | blinded expert judgement of sampled claims |

A **failed** result (any cause: your error, `INVALID_OUTPUT`, `TIMEOUT`, a crash, no result)
scores 0 in A and in B for that case.

### 13.2 A — TRL decision (45%)

Per case, then the mean over all scored cases:

| Your result | Experts give a TRL | Experts find no TRL determinable |
|---|---|---|
| `completed`, exact TRL | 1.0 | — |
| `completed`, off by 1 | 0.5 | — |
| `completed`, off by 2 or more | 0 | — |
| `completed`, inside the experts' interval | — | 0.5 |
| `completed`, outside the interval | — | 0 |
| `abstained` | 0.25 | 1.0 with a reason the experts accept, 0.75 with another reason |
| `failed` | 0 | 0 |

So when a TRL can be determined the order is **exact > off by 1 > abstain > off by 2 or more =
failed**: abstaining is better than a wrong guess but worse than a near miss. When the experts find
no TRL determinable, an abstention with the right reason earns full points.

### 13.3 B — criterion evidence (40%)

The experts label every criterion of every hidden case `met`, `not met` or `insufficient
evidence`, and for each `met` criterion they list the **gold pages** that support it. For scoring,
the labels collapse to two kinds:

- **met part**: a criterion the experts label `met` counts as a hit when you also say `met`
  **and** at least one of the **first 3 distinct (document_id, page) items** in your evidence
  list is a gold page. Pages after the first three distinct ones are not looked at, so put your
  best evidence first.
- **not-established part**: a criterion the experts label `not met` or `insufficient evidence`
  counts as a hit when you do **not** say `met`.

```text
B = (2 × mean(met part) + 1 × mean(not-established part)) / 3
```

Both means are taken over all labelled criteria of all your scored cases together **[to be
confirmed]**; if one part has no criteria, B is the other part.

### 13.4 C — expert review (15%)

From your scored results, 6 `met` claims are sampled at random (the first evidence item of a `met`
criterion: document, page and `supporting_span`). Experts judge them **blinded** (they do not see
the team), reading the cited page:

| Judgement | Points |
|---|---|
| SUPPORTS — the quoted text is on the cited page and supports the criterion | 1 |
| PARTIAL, NOT_SUPPORTS | 0 |
| No `supporting_span` given | 0 |
| FABRICATED — the quoted text is not on the cited page | −1 |

```text
C = max(0, sum of points / max(6, number of judged claims))
```

A team with fewer than 6 `met` claims gets 0 for the missing ones. Rules for evidence:

- The `supporting_span` must be text that is **on the cited page** (as you extracted it; small
  extraction differences are fine). Text that is not there is fabrication.
- **A sentence that only asserts a TRL number** ("the system has reached TRL 6") **is never
  evidence** for a criterion: it is judged NOT_SUPPORTS. Evidence describes what was built,
  tested or demonstrated, where, and with which result.
- The size and scope of the fabrication penalty are a default **[to be confirmed]**.

### 13.5 Baseline, standard errors, ranking and finalists

- The organizer publishes the score of the **always-abstain baseline** (a module that abstains on
  every case with `insufficient evidence` and claims no criterion), scored by the same rules.
- Each team's score is published with its **standard error** (a paired bootstrap over the cases,
  1,000 resamples, C held fixed).
- Ties are broken by B, then A, then C, then fewer failed cases **[to be confirmed]**.
- **Finalists**: the top 40 teams, plus every team whose total is within its standard error of the
  40th total (exact ties always included), are run on **10 more hidden cases** with the same
  submission 3. The Stage 1 ranking and prizes follow the scores on all **20 cases**.

### 13.6 Interim scores (submission 2)

Submission 2 gets the automatic parts only, A and B by the rules above on the interim cases, and
their total renormalised to the 45:40 weights, `(0.45 × A + 0.40 × B) / 0.85`, privately for your
team **[to be confirmed: this form]**. There is no C, no rank and no standard error, and the
interim score does not count towards the result.

### 13.7 Expert review after the final submission, and appeals

- The hidden cases are fixed before the final-submission deadline. The expert labels may be
  written after the deadline, on those fixed cases.
- After automatic scoring, the experts review every page that **at least 5 teams** cited for a
  `met` criterion (within their first 3 distinct pages) but that is not a gold page. Pages the
  experts accept are added to the gold set **for every team**, and all teams are re-scored.
- After the provisional results, a **48-hour appeal window** opens for one type of appeal only:
  "page X of document D in case K supports criterion C". An accepted appeal adds the page to the
  gold set for every team. Other appeals (for example against a TRL label) are not accepted
  **[to be confirmed]**.

The organizer's scoring tools are not part of this kit; the kit never scores and holds no answers.

## 14. Stage 2 — web system and demonstration

**What the organizer prepares.** For every advancing team, the organizer sets up an event computer
with the pinned kit, the common base environment, the model store and the team's **final Stage 1
package, unchanged** (the same package hash as its submission 3). The kit server runs the package
as in Stage 1. The computers have no network.

**What you build.** A web system for an assessor that uses your frozen Stage 1 package through the
kit server's HTTP API (`POST /v1/assessments`, then `GET` the job): the user gives technical
reports and gets the TRL and, for every criterion, its status with the evidence pages shown next
to the page of the original PDF. You may not retrain or replace the package for Stage 2. You upload
your web code before the event; on the event computer it is merged with the prepared setup and
demonstrated there, offline. Who performs the merge (the team on site, with the organizer
present) is **[to be confirmed]**.

**Environment.** Your web system runs in the same common base environment: its Python code may use
only base packages (fastapi, uvicorn, jinja2, python-multipart, httpx and pydantic are in the
base); there are no additional packages for Stage 2. Front-end libraries, fonts and icons are
bundled with your code (no CDN, no external fonts or analytics). Upload the front-end sources with
`package.json` and `package-lock.json`, and the built output, so that nothing needs to be installed
from the network on the event computer **[to be confirmed: whether Node.js is available there]**.

**Gate.** A Stage 2 system is scored only when it passes all of these:

1. it starts offline on the event computer from the uploaded code;
2. it assesses through the kit server with the team's frozen Stage 1 package (the job's
   `verified_package_sha256` equals the one of submission 3);
3. it shows the TRL and every criterion's evidence page next to the original PDF page;
4. the licence checker finds no refused component (`tools/check_licenses.py --web`).

**Rubric** (100 points) **[to be confirmed]**:

| Item | Points |
|---|---|
| Evidence presentation and traceability (pages opened in the original PDF, quoted spans, missing evidence and abstention reasons explained) | 30 |
| Usability for an assessor (from reports to a reviewed assessment, clarity, handling of `abstained` and `failed`) | 30 |
| Integration and robustness (frozen pipeline, several documents, busy server, time-outs, errors, offline) | 20 |
| Demonstration and documentation (live demonstration, README, licence notices and an About page) | 20 |

**Final score** of a Stage 2 team **[to be confirmed]**:
`final = 0.6 × Stage 1 total (20-case scoring) + 0.4 × Stage 2 rubric / 100`. The number of
advancing teams is announced by the organizer.

## 15. Licences and intellectual property

The organizer confirmed the licence rules on 2026-10-10 (decision D53):

- Your own work (Stage 1 code, rules and trained weights; Stage 2 web code) is licensed under
  **Apache-2.0 or MIT**, with the full text in `participant_module/LICENSE` (Stage 2: `LICENSE` at
  the root) and the same identifier in `submission.json` `"license"`.
- Third-party components: strong copyleft (AGPL, GPL, SSPL, EUPL, OSL, RPL), non-commercial,
  research-only, revenue-capped and commercial-only licences are refused; weak copyleft is
  reviewed after the submission; MPL-2.0 is allowed.
- Public models: only the catalogue (§8.4). PyTorch, triton and NVIDIA's CUDA libraries are part
  of the base, installed by the organizer and never shipped by you.
- **Third-party pure-Python modules** may be included in your package (copied into
  `participant_module/`, each listed with its licence in `participant_module/THIRD_PARTY_NOTICES.md`;
  compiled extensions are refused). **If a licence problem or a security problem with code you
  included arises later, your team bears the legal responsibility and the award is revoked**
  (decision D66, 2026-10-10). Passing the kit's checks does not mean the code is free of licence
  or security problems; `tools/make_submission.py` prints this reminder every time it packs or
  checks your zip.

On 2026-10-10 the organizer also decided (D54) that you submit your work as **open source** and do
not assert patent, copyright, trade-secret or other intellectual-property claims over it against
the organizer, APCTT or anyone who uses it under that licence; you keep ownership. The clause
wording is under the organizer's legal review, and the official participation terms prevail.
`tools/check_licenses.py` flags components from their declared metadata; it is not legal advice.
Details: [LICENSING.md](LICENSING.md).

## 16. Eligibility and disqualification

**Eligibility** **[to be confirmed]**: teams registered by the registration deadline whose members
accept the participation terms (including the licences of this kit and of the base environment,
§15); one team per person; organizer staff, the people who prepare the hidden cases and the experts
do not take part.

**Disqualification** (defaults; the official terms prevail) **[to be confirmed]**:

- trying to reach the network, the hidden cases or labels, other teams' files or the organizer's
  systems, or interfering with the server, the machine or the time measurement (for example
  detached processes);
- answers obtained from the hidden cases or labels by any route other than your module's own
  assessment of the case it receives;
- declaring third-party or public weights as team-trained, shipping refused components, or leaving
  refused licence items unresolved;
- submitting another team's work, or work you have no right to submit.

A failed or invalid result is not a disqualification: it scores 0 for that case. A licence or
security problem in third-party code you included that arises later leads to the revocation of the
award (decision D66, §15).

## 17. FAQ

**Can we use only the CPU?** Yes. `compute.device` `cpu` is fully allowed and scored by the same
rules and the same 3-minute limit. The catalogue marks the models that are practical on a CPU.

**Do we need a GPU to develop?** No. `tools/make_env.py` builds a CPU development base with the
same package versions on macOS and on Linux or WSL2 without an NVIDIA GPU. The 4-bit catalogue
models need a CUDA GPU.

**Can we use other public models?** No. Only the models of the catalogue (§8) are available at the
event, offline, and public model weights may not be shipped in your zip. There is no request
procedure for adding a model.

**Can we fine-tune a catalogue model or train adapters?** Yes. Ship the weights you trained (for
example LoRA adapters) in `assets/`, declare them in `submission.json` `models[]` with
`"team_trained": true`, their `path` and the catalogue id of the model you started from in
`base_model`. Your module loads the base model from `APCTT_MODEL_STORE` and your weights from
`asset_root`. License your weights under Apache-2.0 or MIT; they count towards the 2 GB cap.

**Can we add Python packages?** Not as packages: the base is fixed for everyone. You may copy
third-party pure-Python modules into `participant_module/` with their licences in
`THIRD_PARTY_NOTICES.md`; your team bears the responsibility for them (decision D66, §15).
Compiled extensions, wheels and virtual environments are refused.

**How large may the submission be?** 2 GB, for every team. Weight files over 50 MiB must be
declared as team-trained in `models[]`.

**Can we get an exception or an advance check of our package?** No. Nothing is approved in
advance and there are no exceptions (§9). Check your package yourself with
`tools/make_submission.py`, which runs the organizer's intake checks, and use submissions 1 and 2
for feedback.

**What if we miss a submission?** Missing submission 1 or 2 only loses that feedback **[to be
confirmed]**. Missing submission 3 means your team is not scored and not ranked: no earlier
submission is used instead.

**What if a case takes longer than 3 minutes?** It is stopped and scores 0 in A and B. It is not
re-run. Stop early with `context.remaining_ms()`, and time the load of large models (§8.3).

**Do abstentions help?** When the experts find no TRL determinable, an abstention with an accepted
reason scores 1.0. When a TRL is determinable, an abstention scores 0.25 (better than a TRL off by
two or more). The always-abstain baseline is published so you can compare.

**Can we use native Windows?** No; use WSL2. macOS works for development.

## 18. Points the organizer must still confirm

Everything marked **[to be confirmed]** above:

- the dates, the official checklist, the official input limits and the machine specification (5
  machines of the reference type);
- that submissions 1 and 2 are optional, one upload per submission round, when their results come
  back, the `evaluation` profile for all three runs, and the numbers of cases (3, 5, 10, +10);
- that a refused submission 3 counts as no final submission;
- that public models outside the catalogue cannot be used because they are not available offline
  and public weights may not be shipped (the reading of decision D64);
- how general questions about the rules are answered for all teams;
- the scoring weights and constants of §13, pooling B over all criteria, the fabrication penalty,
  the tie-break order, the form of the interim score, and that only page appeals are accepted;
- Stage 2: who performs the merge on the event computer, whether Node.js is available there, the
  rubric, the number of advancing teams and the final-score weights 0.6 / 0.4;
- the eligibility and disqualification rules of §16.

## 19. Where to go next

| Guide | For |
|---|---|
| [README.md](../../README.md) | Step by step: kit, base environment, models, module, submission |
| [MODEL_CATALOG.md](MODEL_CATALOG.md) | Every catalogue model: size, VRAM estimate, CPU option, use |
| [MODULE_GUIDE.md](MODULE_GUIDE.md) | Writing the module; the worker environment, model store and time limit |
| [DATA_CONTRACT.md](DATA_CONTRACT.md) | Every input and output field and rule |
| [SUBMISSION.md](SUBMISSION.md) | The three submissions, the bundle, the data declaration and handover |
| [LICENSING.md](LICENSING.md) | Licences of your work, of copied code and of models; the licence checker |
| [CONFIGURATION.md](CONFIGURATION.md) | The local server configuration |
