# Submission, data declaration and handover

kit 0.4.0

This page lists what you send to the organizer and when: the three submissions, the zip, the data
declaration and the handover items. The submission channel, deadlines and the official checklist
are announced by the organizer separately; they are not part of this kit. The challenge as a whole,
including how submissions are run and scored: [PROBLEM_DESCRIPTION.md](PROBLEM_DESCRIPTION.md).

## 1. What you send, and what comes back

### 1.1 Three submissions

| Submission | Cases it runs | What you get back | Scored |
|---|---|---|---|
| 1 — check | The public sample cases | PASS or FAIL, and per case: status, TRL, error code, the server's fixed failure sentence, output issues (path and rule), warning codes, timings | No |
| 2 — interim check | A separate interim case set, never reused in the final set | The same diagnostics, plus your automatic scores A and B and their total renormalised to 45:40, privately (no expected answers, no per-case scores) | No (not counted) |
| 3 — final | The frozen hidden set (and 10 more hidden cases for finalists) | A receipt: accepted or refused, the hashes of your zip and package, the base and the models | **Yes: the only scored submission** |

Each submission is the same kind of zip, made with `tools/make_submission.py` (§1.2), and is
checked in full at intake with the same published rules for every team. Passing submission 1 or 2
is feedback, never an approval: nothing is approved in advance, and there are no exceptions. A
refused zip comes back with the reasons. **Only submission 3 is scored: a team without a
submission 3 is not scored or ranked, and no earlier submission is used instead.** Between
submissions you may change your code, rules and catalogue models; what you send as submission 3 is
what is run and scored. The defaults that the organizer has not yet confirmed (for example the
numbers of cases, and that a refused submission 3 counts as none) are listed in
[PROBLEM_DESCRIPTION.md](PROBLEM_DESCRIPTION.md) §18.

### 1.2 The submission zip

You submit **no environment**. Every team's module runs in the common base environment (the same
for everyone, read-only, identified by `base_id`) and reads public models from the organizer's
read-only model store ([PROBLEM_DESCRIPTION.md](PROBLEM_DESCRIPTION.md) §7–8).
`tools/make_submission.py` packs `<team>_submission.zip` from your submission folder. It takes only
these entries and leaves everything else out:

| Entry | Contents |
|---|---|
| `participant_module/` | Your code and rules: `__init__.py`, `adapter.py` (entry point `participant_module.adapter:AssessmentModule`), `LICENSE` (Apache-2.0 or MIT), `THIRD_PARTY_NOTICES.md` ([LICENSING.md](LICENSING.md) §2), and any third-party pure-Python modules you copied in (§5) |
| `assets/` | Only weights and rules your team trained or wrote (may be empty); passed to `load()` as `asset_root` |
| `submission.json` | `submission_version`, `team`, `package_id`, `package_version`, `base_id`, `declared_package_sha256`, `license`, `compute`, `settings` and `models` (`contracts/submission.schema.json`) |
| `declaration.json` | The data declaration (§3) |
| `README.md` | What your module does and how it was built |

- `base_id` is the common base of this kit (`contracts/base-environment.json`); another value is
  refused.
- `compute.device` is `cpu` or `cuda:0` (CPU-only is fully allowed); `settings` is passed to
  `load()` as `config["module"]["settings"]`.
- `models` lists every public model your module loads, by `catalog_id` from the model catalogue
  (`contracts/model-catalog.json`, `python tools/get_models.py --list`): the organizer provides
  these in the model store, so a catalogue entry has no `path` and its weights are never in your
  zip. A model outside the catalogue is refused, whatever its licence.
- `models` also lists the weights your team trained and ships in `assets/` or
  `participant_module/`: `{"name", "path", "team_trained": true}`, optionally with `license`
  (Apache-2.0 or MIT), `sha256` and `description`. A fine-tune or adapter of a catalogue model
  names it in `base_model` (a catalogue id). Every weight file over 50 MiB must be covered by such
  an entry. A copy of a catalogue weight file is refused even when declared here: the catalogue
  records the size and sha256 of every catalogue weight file, and the tool compares every file of
  the bundle with them.
- `declared_package_sha256` is the package hash of `participant_module/` and `assets/`, the same
  value as `verified_package_sha256` of the server ([CONFIGURATION.md](CONFIGURATION.md) §5). The
  tool computes it and writes it into `submission.json` (and into `declaration.json` when that file
  has the key); leave it `null` until then.

### 1.3 Size and what is refused

The zip may be at most **2 GB** (2,000,000,000 bytes), the same fixed cap for every team.
Catalogue models do not count: they are in the model store. Refused: other top-level entries;
symbolic links; compiled extensions and binaries (`.so`, `.pyd`, `.dylib`, `.dll`, `.exe`), wheels,
virtual environments, `site-packages`, installed package metadata, `.git` and `node_modules`;
copies of base packages (a folder named like a base package's import name); any file with the bytes
of a catalogue weight file, whatever its name or declaration; undeclared weight files over 50 MiB
(an undeclared weight file under 50 MiB that looks like a public model is a licence review item,
decided by the organizer after the submission); a missing required file; a `submission.json` that does not follow the schema; a
`declaration.json` whose team or package differs; a `base_id` other than the kit's; a model outside
the catalogue; a package hash that differs from the declared one; and anything the licence checker
refuses. The organizer's intake runs the same checks and recomputes the hash.

```bash
.venv/bin/python tools/make_submission.py ../my_submission
.venv/bin/python tools/make_submission.py --check ../MY-TEAM_submission.zip
```

Exit codes: 0 `VALID`, 1 `REFUSED` (each `ERROR` line names a problem; the zip is deleted), 2
`VALID_WITH_REVIEW` (licence items the organizer decides after the submission), 3 usage error.
Every pack and check also prints a `REMINDER` line about third-party code in your package (§5).
How to: [README.md](../../README.md) step 10.

## 2. Using NASA TechPort

Using TechPort is optional and non-exclusive. If you use it:

- Review the related datasets, technical reports, papers and test and verification records that
  are accessible to you, not only the project summary or its TRL fields.
- Do not mix up start, current and target TRL.
- Do not copy a project-level TRL onto every document, subsystem or component of that project.
- Record where each item came from (§3).

Data volume is not scored, training is not mandatory and exhaustive collection is not expected.
The assessment server never crawls or queries TechPort; everything your module needs must be in your
package or assets, the common base environment or the catalogue models of the model store.

## 3. Data declaration

For each data source, declare its source, version, date, role, label origin and linked project, and
its licence or terms of use.
If your team did not train anything, declare `no_team_training`. Example structure
([SUBMISSION_DECLARATION.example.json](SUBMISSION_DECLARATION.example.json)):

```json
{
  "declaration_version": "apctt-declaration-example-v1",
  "example_only": true,
  "team": "EXAMPLE-TEAM",
  "package_id": "example-assessment-package",
  "package_version": "0.1.0",
  "declared_package_sha256": null,
  "team_training": "no_team_training",
  "training": null,
  "data_sources": [
    {
      "source": "NASA TechPort (example entry)",
      "version": "public export used by the team",
      "date": "YYYY-MM-DD",
      "role": "retrieval reference for similar projects",
      "label_origin": "project-level start/current/target TRL as published; not used as component labels",
      "linked_project": "TechPort project ID of the referenced project",
      "license": "licence or terms of use as published by the source (name, SPDX identifier or URL)"
    }
  ],
  "inference_assets": {
    "source_code": "participant_module/ (commit or archive hash)",
    "weights": [],
    "prompts_or_rules": ["rules/criteria.yaml"],
    "reference_assets": [],
    "dependency_declarations": ["the common base environment (base_id in submission.json)", "catalogue models listed in submission.json models[]"]
  },
  "notes": "Example structure only. Replace every value; keep keys you use and state what does not apply."
}
```

| Field | What to write |
|---|---|
| `team`, `package_id`, `package_version` | Your team and package identity; `package_id` as in your configuration. |
| `declared_package_sha256` | The package hash; `tools/make_submission.py` fills it in when the key is present. |
| `team_training` | `no_team_training` if you trained nothing; otherwise describe it in `training`. |
| `training` | If you trained: training code location, configuration, data sources used, seeds, hardware. |
| `data_sources[].source` | Name of the source (dataset, report collection, database). |
| `data_sources[].version` | Release, export or access version. |
| `data_sources[].date` | Date you obtained it. |
| `data_sources[].role` | How you used it: training, validation, retrieval reference, rules, examples. |
| `data_sources[].label_origin` | Where any labels came from and what they mean (e.g. project-level current TRL). |
| `data_sources[].linked_project` | The project the material belongs to, if any. |
| `data_sources[].license` | The licence or terms of use of the source: an SPDX identifier, a licence name or the URL of the terms ([LICENSING.md](LICENSING.md) §5). |
| `inference_assets` | Everything needed to run inference (§4). |

The example is a structure, not a required schema; the organizer will announce the official
declaration format.

## 4. Handover

Link your execution package and follow-on development materials by version and hash:

- inference source code;
- weights;
- prompts or rules;
- reference assets;
- dependency declarations (the `base_id` of the common base and the catalogue models you use, by
  `catalog_id`; your submission contains no packages);
- if your team trained a model: training code, configuration and data information; otherwise
  `no_team_training`.

The Stage 2 application uses the same frozen assessment pipeline, so the package you hand over must
be the one that produced your assessment results.

## 5. Licence of your work

The kit's MIT licence covers the kit only. Your module, weights, rules and data remain yours. So that
the organizer can run, demonstrate, keep and hand over your work (§4), these rules apply; the
organizer confirmed them on 2026-10-10 (decision D53), and the official participation terms will
carry them:

- License your own code, rules and trained weights under Apache-2.0 or MIT: put the licence text in
  `participant_module/LICENSE` and the same identifier in `"license"` of `submission.json`. The same
  rule applies to the code of your Stage 2 web system (`LICENSE` at its root, and `"license"` in
  your `package.json` if you set it). Any other licence, or a missing declaration or licence file,
  is refused.
- Use only third-party packages, front-end libraries, fonts and models whose licences the policy
  allows, and list them with version and licence in `participant_module/THIRD_PARTY_NOTICES.md`.
  Strong copyleft (AGPL, GPL, SSPL, EUPL, OSL, RPL), non-commercial, research-only,
  revenue-capped and commercial-only components are refused; weak copyleft (LGPL, EPL, CDDL) is
  reviewed; MPL-2.0 is allowed.
- Use public models only from the model catalogue (`contracts/model-catalog.json`, named in
  `submission.json` by `catalog_id`; any other public model is refused and public model weights
  are never shipped), and declare the licence of every data source (§3).
- You may copy third-party pure-Python modules into `participant_module/`, each listed with its
  licence in `participant_module/THIRD_PARTY_NOTICES.md`; compiled extensions are refused. If a
  licence or security problem with code you included arises later, your team bears the legal
  responsibility and the award is revoked (decision D66, 2026-10-10; [LICENSING.md](LICENSING.md)
  §2.2).
- Ship no packages at all: PyTorch, NVIDIA CUDA packages and every other package come from the
  common base environment, which the organizer installs.

You keep ownership of your work. By submitting it under Apache-2.0 or MIT you submit it as open
source, and you do not assert, and will not assert, patent, copyright, trade-secret or other
intellectual-property claims over the submitted work, including its follow-on development, against
the organizer, APCTT or anyone who uses it under that licence; you warrant that you have the right
to submit everything in your submission; third-party components keep their own licences. The
organizer decided this on 2026-10-10 (decision D54); the clause wording is under the organizer's
legal review and the official participation terms prevail. The clause, and what Apache-2.0 and MIT
already provide (Apache-2.0 has an express patent licence, MIT has none): [LICENSING.md](LICENSING.md)
§2.1.

The licence checker `tools/check_licenses.py` only flags components from their declared metadata;
your team remains responsible for what it submits, and the organizer decides the flagged items after
the submission.
What is allowed, what is refused, permissive alternatives, what the checker does and does not
check, and how to run it: [LICENSING.md](LICENSING.md). Neither this page nor the checker is legal
advice.

## 6. Final check

Work through the list in [MODULE_GUIDE.md](MODULE_GUIDE.md) §9, then confirm:

- [ ] `tools/make_submission.py ../my_submission` ends with `VALID`, or with `VALID_WITH_REVIEW`
      and you can explain each review item ([LICENSING.md](LICENSING.md) §7).
- [ ] `submission.json` names the kit's `base_id`, your device, and every catalogue model and
      team-trained weight your module loads.
- [ ] `GET /v1/package` shows your `package_id` and `verification_status: verified`, and its
      `verified_package_sha256` equals the `declared_package_sha256` the tool wrote.
- [ ] Your declaration lists every data source, its licence and the label origin of any labels you
      used.
- [ ] Your handover links match the exact files you submit.
- [ ] For the final round: your zip is uploaded as **submission 3** before the deadline.
