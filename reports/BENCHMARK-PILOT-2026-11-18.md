# Compiler-indexed C++ benchmark pilot

This is a fresh two-TU diagnostic run on macOS arm64 with Clang 22.1.8.
[Machine-readable evidence](benchmark-pilot-2026-11-18.json) retains input,
inventory, object, worker and capture provenance. This pilot exercises build
preparation and failure accounting; it is not the complete benchmark release.

## Inputs and function inventory

Both projects are outside the previous ten-project/4,580-definition cohort.
Each full checkout is clean at its exact commit. Actual CMake compile commands
are retained, and both original/prepared sources pass compiler syntax checks.
Each selected TU also compiles to a verified Mach-O AArch64 object.

| Cell | Pinned project revision | Scope | Compiler-observed groups | Withheld | Requested |
| --- | --- | --- | ---: | ---: | ---: |
| AsmJit arena.cpp, C++20 | `0464e1c8f1f43c861a0c73d4e59437fff255cdd9` | Primary implementation file | 17 | 0 | 17 |
| GoogleMock gmock-all.cc, C++17 | `cd8e73f067129f8489e35c7b51c7a68552b289d2` | Project-owned implementations and headers | 1,627 | 24 | 1,603 |
| Total | | | 1,644 | 24 | 1,620 |

Clang JSON ASTs supply explicit written body candidates. Records sharing the
same written offsets retain their template-representation evidence together.
Twenty-four conflicting name/kind groups are withheld explicitly before either
backend runs. This is a bounded compiler inventory, not an assertion of total
C++ definition completeness. Implicit functions and semantic CFG correctness
are outside its contract.

GoogleMock's amalgamation includes other implementation files and headers.
Of its 1,603 requests, 95 belong to included project `.cc` files and 1,508 to
project headers. They are separated in the report. Its primary amalgamation
file itself contributes no written bodies. Foreign/system headers stay in the
prepared input but are outside the requested population. Source line markers
are replaced by blank lines with a retained physical-to-original coordinate
map, so both backends receive exactly the same prepared bytes.

The original CMake request `CMAKE_CXX_STANDARD=17` for AsmJit produces actual
`-std=c++20` compile commands at this revision. A negative control verifies that
the preparation helper rejects admission as C++17. The admitted cell uses the
actual C++20 configuration.

## Parsing, graph availability and reference comparison

Rust-Joern uses the frozen `d248d3934e4b93d4a32dab521e507ce83b019384` candidate
library with SHA-256
`0dea5d357047564928ed1dbfc2ac70a571396a113ccc6ef8c82819ae82dc56cc`.
References use unchanged PyJoern 4.0.150.4 / Joern 4.0.150 in an isolated Python
interpreter and working directory without the replacement shim.

| Cell | Rust strict TU | Rust body CFG / requests | Original body CFG / requests | Compatibility matches / original body CFG |
| --- | --- | ---: | ---: | ---: |
| AsmJit C++20 | Rejected | 16/17 | 16/17 | 16/16 |
| GoogleMock C++17 | Rejected | 204/1,603 | 1,031/1,603 | 184/1,031 |
| Total | 0/2 accepted | 220/1,620 | 1,047/1,620 | 200/1,047 |

Body graph counts come from permissive extraction, with one-to-one alignment
by function name and physical definition range. Missing/ambiguous identities
remain in the requests. Counts do not establish that these graphs are safe for
DecBench scoring. A degenerate graph may represent a genuinely empty body;
it is reported separately rather than automatically called a parser error.

Rust outcomes are 220 body graphs, 57 degenerate graphs and 1,343 unmatched
definitions. Original outcomes are 1,047 body graphs, 225 degenerate graphs and
348 unmatched definitions. The original capture retains full-name/extent rows
instead of a public short-name map; upstream's internal collapse and ambiguous
identity still limit the reference, so an unmatched original row alone does not
prove a missing definition.

On the 203 requests with nondegenerate graphs on both sides, 200 match in
compatibility mode. Default-mode graphs match on 197/203. These are directed
topology/entry/exit comparisons, not statement, binding or effect equivalence.
The common-subset rates must be accompanied by full requested coverage.

GoogleMock has 843 requests with original body CFGs and unmatched Rust rows.
All 95 included implementation-file definitions are unmatched on the Rust
side. The latest aligned Rust record ends at physical line 77,788, while the
original and compiler inventories reach 90,622. This gives a concrete lead for
investigating parser recovery and downstream body loss; it does not establish
that every unmatched row has the same cause.

The earlier 88.25% body availability came from a different, primary-file-only
cohort. Pooling the cohorts as one representative C++ support rate would hide
their different selection and ownership policies.

## Runtime and limitations

Per-call times remain in the JSON as diagnostic traces. Rust calls use an
already-loaded native API; original calls include JVM startup. Unrelated heavy
processes were observed on the host during the work. No controlled speed ratio,
memory regression result or speed-preservation claim is made. Correctness
results and these timing observations remain separate.

Only Clang/macOS arm64 and these C++17/C++20 build cells were exercised here.
GCC, MSVC, Linux, Windows, other architectures and standard modes need their own
captures. SDK/system headers are retained through prepared hashes but are not
a separately frozen/reprovisionable SDK image. Redistribution is unqualified;
raw source, preprocessed headers, ASTs and full captures stay in ignored local
`workspace/benchmark-pilot-2026-11-18/` storage.

## Reproduction and validation

Example preparation after checking out the AsmJit commit and configuring an
out-of-source CMake build with the explicit C++20 mode:

```sh
python3 scripts/prepare_benchmark_case.py \
  --checkout /path/to/asmjit \
  --commit 0464e1c8f1f43c861a0c73d4e59437fff255cdd9 \
  --database /path/to/build/compile_commands.json \
  --source asmjit/axl/arena.cpp --standard c++20 --scope primary \
  --expected-format Mach-O --expected-arch aarch64 \
  --output workspace/asmjit-arena-cxx20
```

For GoogleTest, use its pinned commit, `googlemock/src/gmock-all.cc`, C++17
and `--scope project`. Full configure/preparation commands are retained in
the local recipe and per-cell provenance. The current helper supports direct
Clang GNU-style argv; response files, submodules and native MSVC command
decoding require follow-up work. Existing output directories are refused.

The new tests cover relative compilation databases, duplicate commands,
response-file rejection, actual standard overrides, line markers, overload
preservation, template clones, source ownership, conflicting identities and
invalid AST offsets. Python 3.12 with NetworkX runs the complete corpus suite;
Black, Ruff and diff checks apply to the new files. Original capture/comparison
remain local pilot drivers, not yet the general checkpointed benchmark runner.

Next work should separate GoogleMock's parser recovery failures from identity
alignment errors, reduce a compiler-accepted example and compare it with the
original backend before proposing a focused Rust-Joern fix.
