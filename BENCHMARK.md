# C++ frontend benchmark design v1

Status: local design and audited seed inventory, 2026-11-18. This is a
Rust-Joern/source-CFG benchmark. Its results do not rank binary decompilers.
The machine-readable proposal is [benchmark-v1-plan.json](manifests/benchmark-v1-plan.json).

## Questions and populations

Measure whether a frontend finds the expected functions, preserves their
control flow and observable effects, and does so within the runtime budget.
Publish these answers separately. A successful parser invocation, an emitted
graph and a qualified CFG are different outcomes.

| Track | Inputs | Required evidence | Purpose |
| --- | --- | --- | --- |
| Real projects | Complete, compiler-accepted TUs from pinned open-source revisions | Build commands, dependencies, prepared hashes and independent function inventory | Coverage, scale and practical regressions |
| Language boundaries | Small versioned cases, preferably reduced from real failures | Standard/compiler acceptance, expected functions and explicit control/effect checks | C++98/03, 11, 14, 17, 20 and 23 distinctions |
| Decompiler output | Frozen genuine C/C++-like output, including invalid output | Producer/version, binary and prepared-output hashes, declared language/context contract | Tolerant parsing and recovery without silently losing bodies |
| Stress and mutations | Large real TUs and seeded transformations of known inputs | Parent hash, transformation, seed and checked invariant | Resource limits, hangs, crashes and stability |

Keep C controls in a separate track. Track source-language mode, GNU/MSVC
extensions, compiler version and frontend execution host independently.
Compile failure due to missing headers is a preparation failure. A backend
failure on an admitted input remains in that backend's requested population.

## What exists

The [audited baseline](reports/benchmark-design-baseline-2026-11-18.json)
records two different populations:

* The frozen GitHub discovery manifest contains 300 repositories with 578
  selected raw files, plus two unsuccessful repository inspections. All 578
  local file hashes were checked for this design. Discovery status `ready`
  means source acquisition; it does not mean a buildable TU or qualified CFG.
* The existing regression cohort contains 83 distinct prepared TUs and 4,580
  observed primary-file definition candidates from ten projects. The recorded
  candidate emits 4,042 nondegenerate body CFGs (88.25%). This is a saved-run
  audit, not a fresh backend execution or a semantic correctness rate.

Tree-sitter supplied the latter inventory and can miss definitions. Original
Joern can also collapse records before export. Neither tool's successful
outputs define the benchmark's total function population. Luau contributes
2,081/4,580 candidates (45.44%); publish project-balanced and pooled results.
The existing files have already been inspected and used during development;
none qualifies as an untouched held-out test set.

## Project and build admission

Start with the existing ten-project regression cohort and qualify twelve
additional candidates listed in the plan. They add CLI, server, GUI,
compiler/JIT, numerical/OCR and platform-specific contexts. These are proposed
domain labels, not evidence that a particular C++ feature occurs in a selected
file. Acquire the full pinned checkout and real project build configuration;
the two raw files selected during discovery are only leads.

An admitted build cell must retain:

1. Repository URL and exact commit; project/file licenses and notices; source
   ownership and submodule/dependency commits. Repository SPDX metadata alone
   does not authorize redistribution of every source or generated header.
2. Exact TU, working directory, argv, environment inputs, generated headers,
   compiler/version, SDK/sysroot and container image digest where applicable.
   Prefer the `arguments` form of a compilation database. Hash response files;
   unresolved command ambiguity blocks admission.
3. Explicit standard flag or evidenced compiler default, extension mode,
   target triple and independently checked object format/architecture. An
   experimental reconfiguration remains distinct from an original build.
4. Successful compiler check, original/prepared hashes and the transformation
   log. Preserve source ownership through line markers and a coordinate map;
   identical prepared bytes go to both Joern backends. Retain header context.
5. An independent definition inventory and oracle availability for each
   requested function. Record extraction failures before running backends.

Clang AST/tooling can inventory supported builds; compiler incompatibility is
an explicit oracle limitation. GCC/MSVC-only inputs need compatible evidence
rather than a claimed Clang ground truth obtained with changed macros. Keep
the current Tree-sitter cohort labeled `observed-definitions` until its
inventory is reconciled with an independent compiler inventory.

Function identities include revision, build-cell/input hash, file ownership,
source extent and declaration identity where available. Name-only maps cannot
represent overloads, nested methods or lambdas. Preserve every returned record;
duplicate or ambiguous producer identities must not multiply score rows.
Count written template definitions and instantiated specializations in
separate populations, with provenance connecting them. Also separate
project-owned, dependency and compiler-generated functions.

## Standards and platforms

Use only build cells supported by each project. Do not force every modern
project through every legacy language mode. Build standard-specific positive
and negative boundary cases for templates, overloads, inheritance, constructors,
destructors, references, lambdas, constexpr/consteval, concepts, coroutines and
exceptions. Record accepted extensions separately from standard conformance;
compiler acceptance alone does not establish complete frontend support.

The proposed target matrix is Linux x86_64/AArch64, Windows x86_64/ARM64 and
macOS x86_64/arm64. Start with a small common project subset across targets,
plus platform-native projects, to distinguish project effects from platform
effects. Windows x86 is a supplemental legacy profile. Distinguish cross-built
objects, native compilation and native execution evidence. Source CFG analysis
does not need every binary optimization variant to count as a new function.

GCC, Clang/Apple Clang and MSVC profiles keep their actual mode names and
defaults. In particular, do not invent MSVC `/std:c++11` or `/std:c++03` flags.
Original unknown standards stay unknown; the current 83-TU GNU C++17 compiler
check is an experiment, not recovered historical flags.

## Measurements and failure accounting

Every report starts with requested projects, cells, distinct TUs, distinct
content hashes and functions. Report one immutable outcome for every request.
Resume keys include input, backend binary/configuration, schema and oracle
hashes, and validate checkpoint contents before reuse.

| Measurement | Numerator and denominator |
| --- | --- |
| Preparation | Admitted build cells / attempted cells, with every rejection reason |
| Strict TU acceptance | Error-free TU results / admitted requested TUs |
| Function discovery | Unambiguously aligned returned definitions / independently inventoried definitions |
| Body graph availability | Nondegenerate body graphs / requested definitions; trivial/empty bodies are listed separately |
| Qualified CFG coverage | Functions passing the declared evidence and graph checks / requested definitions |
| Joern compatibility | Directed isomorphism with entry/exit roles / functions with an unambiguous original reference |
| Compiler/effect checks | Passing supported checks / functions with sufficient independent evidence, plus evidence coverage / all requests |
| Runtime and memory | Paired timings, throughput and peak RSS for the same frozen work; failures and timeouts remain visible |

Report raw counts, pooled function rates and an equal-project macro average.
Also break down by standard, target, project, function size, branches, nesting
and supported C++ feature tags. Label feature tags by their evidence source.
Report normalized distance distributions only with a frozen graph projection
and distance definition. An empty or constant-return stub control helps expose
how much a coarse topology metric can score without recovering useful work.

Keep these outcomes distinct: backend error/crash, timeout, missing function,
ambiguous identity, degenerate graph, malformed graph, binding/effect mismatch,
topology mismatch, and unavailable oracle. An unavailable oracle retains its
coverage row; a producer failure never becomes an oracle exclusion. Separate
whole-TU strict acceptance from permissive extraction and function-scoped
qualification. A diagnostic outside a body can still affect its declarations;
body-local diagnostic absence is insufficient to declare that CFG reliable.

## CFG and effect evidence

Check node/edge integrity, function entry and exits, branch successors,
terminal transfers and intentionally unreachable regions. Record call target,
receiver and argument correspondence where independent evidence exists.
Constructors, destructor cleanup, short-circuit evaluation, throws and loops
need explicit tests for the effects the frontend claims to model. Unknown
virtual targets remain unknown rather than receiving a guessed binding.

Original Joern compatibility and correctness are separate columns. Raw Clang
basic-block CFGs and Joern expression-level graphs have different contracts;
direct GED on those raw representations is not a correctness metric. Freeze
and validate any common projection independently. Preserve order constraints
and effect facts that topology normalization discards, with explicit abstention
where implicit lifetime/exception behavior is not represented.

Use compiler-accepted minimal cases and controlled execution traces for reduced
fixtures where useful. Finite input tests are bounded evidence, not a proof
of whole-function equivalence. Intentional improvements over original Joern
need a divergence record and a focused regression. Reference capture uses
unchanged original Joern in an isolated environment without the replacement
shim.

## Speed preservation

Compare pinned Rust main, pinned Rust candidate and unchanged original Joern.
Retain backend hashes/options and benchmark hardware, OS, workers, memory
limits and background-load observations. Separate preprocessing, tool startup,
analysis and serialization. Measure both cold start and warmed persistent API
execution; do not compare Rust warm calls with JVM cold launches as one ratio.

Use alternating baseline/candidate order and at least ten pairs on fixed inputs;
collect at least twenty samples for reported per-input p95. Publish small/large
TU and graph-size strata, median, p95, throughput, peak process-tree RSS and
paired uncertainty. Reject contaminated timing samples with an explicit rule
and retain them in the artifact. Never terminate unrelated user processes.

Assess two populations: the full fixed workload, including the cost of newly
recovered bodies, and a separately labeled subset whose observable output is
preserved. A fast rejection or fewer emitted bodies cannot earn a speedup.
Track in-process allocation/memory independently from CLI/JVM process memory.

Provisional review budgets: at most 5% median and 10% p95 slowdown, with no
unexplained loss of qualified CFGs or existing matching references. These are
proposed budgets, not measured results. Uncertainty crossing a budget requires
remeasurement; a deliberate correctness/performance tradeoff needs explicit
review. The current noisy timing artifacts do not establish speed preservation.

## Growth and delivery

1. Freeze and audit the current regression population and candidate baselines.
2. Qualify full builds for the twelve additional project candidates, prioritizing
   diverse contexts. Keep failures in the attempted-cell inventory.
3. Target at least 24 build-qualified projects, 100 distinct TUs and 10,000
   independently inventoried written definitions for the first broader release.
   These are planning targets, not current coverage claims. Standard and target
   dimensions have separate attainment counts.
4. Add small standard/semantic fixtures and a new project-level validation
   cohort before using its results to tune fixes. Group forks and shared source
   into the same split; deduplicate exact prepared content across splits. Once
   inspected to guide a fix, a validation case becomes development data.
5. Add real decompiler output and validated seeded mutations as separate
   tracks. Use actual large TUs for stress tests rather than repeated file copies.
6. Freeze versioned dataset releases with manifests, build recipes, licenses,
   input/oracle hashes, exclusions and result schemas. Publish source payloads
   only after their redistribution terms and transitive contents are checked.

Future implementation should remain small: admission/index first, a lossless
checkpointed runner second, topology/effect comparisons third, timing last.
Existing preparation/capture tools can be reused, but their current completion
is not a claim that this full benchmark contract is implemented.

## Technical references

* [Clang compilation database contract](https://clang.llvm.org/docs/JSONCompilationDatabase.html).
* [Clang source-level CFG representation](https://clang.llvm.org/docs/InternalsManual.html#the-cfg-class).
* [Existing 300-project source inventory](https://huggingface.co/datasets/sjkim1127/joern-cpp-github-300).
