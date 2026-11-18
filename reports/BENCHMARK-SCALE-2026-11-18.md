# Rust-Joern coverage across 311 C++ repositories

This run combines a 300-repository raw source diagnostic and a separate
compiler-checked prepared source comparison. Eleven of the 36 repositories in
the prepared source comparison are outside the raw inventory. The union counts
311 distinct repository names. Project and source selection are exploratory.

The source inventory spans repositories created between 2008 and 2026 and
includes tools, GUI applications, servers, compilers, libraries and embedded
code. The creation date describes the repository. Actual C++ language modes
are tracked separately where a compiler check is available.

## Raw source recovery

Both modes ran all 578 hash-verified files from the fixed 300-repository
inventory with the same release CLI. File counts include inputs that produced
no function rows. The permissive run exported 26,473 function records. This
count includes any duplicate identities and declarations returned by the CLI.

| Run | Files with function records | Files with no functions | Rejected files | Repositories with function records |
| --- | ---: | ---: | ---: | ---: |
| Raw strict | 1 | 4 | 573 | 1 |
| Raw permissive | 548 | 30 | 0 | 299 |

Neither raw run observed a crash or timeout. Each emitted edge referenced
an existing node. Compiler options and dependency context are unknown for
these raw inputs. Their outcomes measure recovery on incomplete inputs.

Clang standalone GNU C++17 validation accepted 14 files across 12
repositories. It reported a missing header or file in 556 of 564 rejected
files. The remaining eight contained other compiler diagnostics. Strict
Rust-Joern rejected eight of the 14 accepted files and emitted no functions
for the other six. Full project build context remains the main constraint on
admitting this inventory for CFG evaluation.

## Prepared source comparison

The archive contains real GCC 13.3 Linux AArch64 O0 builds. We selected up to
two TUs with distinct main source files per project, starting near the median
file size. The main pass uses implementation files. A supplementary pass
includes tests and examples for projects lacking a usable primary implementation
file, plus three projects with relative compiler line markers. The project-level
artifacts record the selected paths for both passes.

GCC rechecked the archived original and the exact prepared bytes in a pinned
container. It accepted 67 of 70 candidate TUs, 55 in the GNU C++17 validation
mode and 12 in GNU C++20. The container uses the original compiler family and
architecture. The validation modes do not establish the original per-TU flags.
Both Joern backends ran on macOS arm64 using the same prepared bytes. The source
target of this campaign is Linux AArch64.

The prepared population uses 1,475 primary-file definition candidates found by
Tree-sitter with ownership from compiler line markers. The inventory is frozen
ahead of either backend. Function alignment requires a unique producer row and
the same name and physical source extent. An unmatched definition can reflect a
parser omission or an unresolved identity. Directed topology comparisons
preserve entry and exit roles. Behavior, call binding and side effects require
independent semantic checks.

| GCC validation mode | TUs | Requested functions | Rust strict TUs accepted | Rust body CFGs | Original Joern body CFGs |
| --- | ---: | ---: | ---: | ---: | ---: |
| GNU C++17 | 55 | 1,172 | 0 | 974 | 1,005 |
| GNU C++20 | 12 | 303 | 0 | 299 | 0 |
| Total | 67 | 1,475 | 0 | 1,273 | 1,005 |

Original PyJoern returned empty exports on all 12 TUs in the GNU C++20
validation group. All 55 other captures returned records. The pooled
body-availability totals reflect this cohort's composition and both frontends'
recovery behavior. In the GNU C++17 group alone, original Joern emitted 31
more body CFGs.

Both backends supplied body CFGs for 928 definitions. Rust compatibility
mode matched 910/928 directed topologies (98.1%) and its default mode matched
874/928 (94.2%). Across all 1,005 original body CFGs, compatibility mode
matched 910, differed on 18, lacked an aligned Rust definition for 76, and
had a degenerate Rust graph for one. The original reference was unavailable
or degenerate on the remaining 470 functions.

FlatBuffers' `idl_gen_text.cpp` and `idl_gen_fbs.cpp` account for 60 of the
76 original body CFGs missing from the Rust comparison. None of their 61
primary-file definitions appears in the Rust export. For `idl_gen_text.cpp`,
the last exported function ends at physical line 96,645 and the first primary
definition starts at line 98,815. This points to body discovery or parser
recovery before CFG construction. The precise cause needs a reduced case.

The machine-readable report retains per-project counts and timing summaries.
Rust times cover a loaded API call and graph capture. Original times include
JVM startup. Both were recorded during concurrent execution. Those timings
support diagnostics and leave the controlled speed comparison open.
[Machine-readable report](benchmark-scale-2026-11-18.json)

## Reproduce the raw diagnostic

Use the original inventory with its sibling `inputs/` directory and a frozen
Rust-Joern CLI:

```sh
python3 scripts/run_github_cpp.py --inventory /path/to/manifest.json \
  --binary /path/to/rust-joern --output workspace/raw-strict --workers 3
python3 scripts/run_github_cpp.py --inventory /path/to/manifest.json \
  --binary /path/to/rust-joern --output workspace/raw-permissive --workers 3 \
  --permissive
```

The original 300-repository metadata is available in the
[GitHub inventory dataset](https://huggingface.co/datasets/sjkim1127/joern-cpp-github-300).
All original inputs, compiler logs, per-function outcomes and full backend
captures for this run are retained under `workspace/`. Raw and prepared input
results retain their own denominators. The broader target is at least 300
repositories with validated build context and independent function evidence.
