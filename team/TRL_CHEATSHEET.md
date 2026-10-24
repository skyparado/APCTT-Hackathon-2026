# TRL cheat-sheet (Task 9)

The basis for the TRL logic (Task 13) and for hand-labelling test cases (Task 8). The kit only
defines the two ends of the scale (1 = basic principles observed, 9 = proven in operational use),
so the middle levels follow the standard NASA (NPR 7123.1) / EU Horizon definitions. Adjust once
the official checklist is published: its criteria will likely map onto these rows.

A TRL is always **relative to the case's `intended_application` and `intended_environment`**.
"Tested in the field" only counts as TRL 7+ if that field is the intended environment.

## The scale

| TRL | Name | What must have been **built** | What must have been **tested**, where | Result that counts | Keywords that suggest it |
|---|---|---|---|---|---|
| 1 | Basic principles observed | Nothing; a paper idea or observed phenomenon | None, or literature review | Principle described / reported | "principle", "phenomenon", "theoretical", "literature review", "we propose", "hypothesis" |
| 2 | Concept formulated | A concept, design or application idea; maybe models/simulations | Paper studies, analysis | Application identified, feasibility argued (not yet shown) | "concept", "conceptual design", "potential application", "feasibility study", "could be used", "analytical model" |
| 3 | Proof of concept | Separate pieces / lab breadboard of the critical function | Lab experiments on the **critical function**, not the whole system | Measured data confirms the key prediction | "proof of concept", "laboratory experiment", "bench test", "breadboard", "preliminary results", "validated the model" |
| 4 | Validated in lab | Low-fidelity components **integrated together** | Lab, as a working ensemble | Integrated components work together | "integrated", "laboratory prototype", "breadboard validation", "component testing", "test bench", "subsystem" |
| 5 | Validated in relevant environment | Higher-fidelity components / breadboard | **Relevant (simulated realistic) environment** | Components work under realistic conditions | "relevant environment", "simulated conditions", "environmental test", "thermal vacuum", "wind tunnel", "hardware-in-the-loop", "high-fidelity" |
| 6 | Demonstrated in relevant environment | **System/subsystem prototype** (representative model) | Relevant environment, as a whole system | Prototype performance demonstrated | "prototype demonstrated", "engineering model", "system-level test", "representative prototype", "pilot", "demonstrator" |
| 7 | Demonstrated in operational environment | Near-final **prototype** at or near planned scale | **Actual operational environment** (flight, field, plant, clinic) | Prototype works in real conditions | "field trial", "flight test", "operational environment", "in-situ", "pilot plant", "deployed prototype", "on-orbit demonstration" |
| 8 | System complete and qualified | **Final system**, in its final form | Test and demonstration against requirements (qualification) | Passes qualification / certification / acceptance | "qualified", "qualification test", "certified", "acceptance test", "flight-qualified", "meets all requirements", "production unit" |
| 9 | Proven in operational use | Final system in **real use** | Successful mission / operations / commercial use | Proven over actual operations | "in service", "operational use", "successful mission", "commercially deployed", "in production", "routine operation", "customers" |

## Telling neighbours apart (where off-by-one errors happen)

| Boundary | Ask this | Lower if... | Higher if... |
|---|---|---|---|
| 2 vs 3 | Is there **measured data**? | only analysis, simulation, "could" | an experiment produced results |
| 3 vs 4 | Were the pieces **integrated**? | one critical function tested alone | multiple components run together |
| 4 vs 5 | **Where** was it tested? | ordinary lab bench | realistic simulated conditions (temperature, vibration, vacuum, load, real samples) |
| 5 vs 6 | Components or a **whole system**? | components / breadboard | full system or subsystem prototype |
| 6 vs 7 | **Relevant** or **operational** environment? | simulated / test facility | the real intended environment |
| 7 vs 8 | Prototype or **final** form? | prototype, near-final | final configuration, formally qualified |
| 8 vs 9 | Tested or **used**? | qualification / acceptance tests | real operations / mission / sales |

## Traps (do not count these as evidence)

1. **TRL statements.** "The system reached TRL 6" is never evidence: the expert review scores it
   NOT_SUPPORTS (PROBLEM_DESCRIPTION §13.4). Skip any sentence whose only content is a TRL number.
   It may still be a *hint* for where to look, but the quote must describe what was built, tested,
   where, and the result.
2. **Plans and goals.** "Will be tested", "is planned", "target TRL 7", "future work", "aims to"
   describe intent, not achievement. Watch the verb tense.
3. **Start / current / target TRL.** Project summaries (e.g. NASA TechPort) list all three. Only
   *current* matters, and only if backed by reported work (SUBMISSION §2).
4. **Project-level vs component TRL.** A project at TRL 6 does not make every component TRL 6.
   Judge the technology the case is about.
5. **Someone else's work.** Literature-review sections describe prior art, not this technology.
   "Previous studies showed..." is not evidence for the case.
6. **Wrong environment.** A successful field test in a different environment than
   `intended_environment` is relevant-environment (5-6), not operational (7).
7. **Simulation only.** Simulations support TRL 2-3 at best on their own; a simulated *environment*
   with real hardware is different (that is 5-6).
8. **Tests without results.** "We conducted vibration testing" without saying it passed or what
   was measured is weaker than "survived 14 g with no degradation". Prefer sentences with a result.
9. **Negative results.** "The prototype failed to reach the target efficiency" is evidence that the
   level was *not* reached.

## Rules of thumb for the decision logic (Task 13)

- **Highest level with real evidence.** TRL = the highest row whose build + test + result are all
  supported, provided the levels below are not contradicted. Higher-level evidence implies the
  lower levels (a flight-tested prototype was lab-tested at some point) even if the report
  skips them.
- **Guess between neighbours, don't abstain.** Scoring (§13.2): exact 1.0, off by one 0.5,
  abstain 0.25, off by two 0. If torn between two adjacent levels, pick one. Abstain only when the
  spread is two or more levels, or there is no build/test evidence at all.
- **Abstention reasons** (exact strings): `insufficient evidence` (nothing was built/tested, or
  reports too thin), `conflicting evidence` (documents disagree by 2+ levels), `ambiguous scope`
  (unclear which technology/component is assessed), `out of scope` (not a technology report).
- **Multiple documents.** Take the most advanced *achieved* result across documents, but check
  dates/versions: a later report showing failure overrides an earlier success.
- **Best sentence first.** Only the first 3 distinct pages per criterion are scored (§13.3). A
  sentence with what + where + result beats one with only what.
