# Compiler-indexed C++ replay across three new projects

Five translation units from the 1,000-repository inventory were built with
Clang 22.1.8 on macOS arm64. Ruckig and CharLS use their pinned CMake compile
commands with optional targets disabled. The CharLS configuration also turns
off precompiled headers. Im3d uses a direct compile command with its shipped
headers. The preparation pass checks both the original and prepared TU,
verifies the output object architecture, and freezes the primary-file
function inventory from Clang ASTs before either frontend runs. The five
inventories contain 259 written function candidates and zero withheld
identity groups.

| Project and standard | TUs | Requested functions | Main body CFGs | With #29 and #37 | Original Joern body CFGs | Candidate topology matches |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Ruckig, C++20 | 2 | 21 | 0 | 19 | 19 | 19 |
| CharLS, C++17 | 2 | 79 | 70 | 70 | 72 | 68 |
| Im3d, C++11 | 1 | 159 | 136 | 136 | 136 | 126 |
| Total | 5 | 259 | 206 | 225 | 227 | 213 |

The table uses permissive Rust-Joern with original Joern compatibility
options and directed topology with entry and exit roles. Original
PyJoern 4.0.150.4 runs separately on the exact same prepared bytes. Main
and #29 alone produced the same aligned outcomes on these five TUs. Both
the #29 build and the stacked build reject all five TUs in strict mode.
Compiler evidence establishes the input population and original Joern supplies
the topology reference. Execution semantics and controlled speed are outside
this measurement.

The stacked draft uses the existing expression-boundary solution as a
prerequisite and adds C++ tokenization for template arguments such as
`Wrapper<::ns::Type>`. The new commit restores all four CFGs in the
Clang/GCC-accepted lexical reduction. The existing boundary PR reproduces the
three CFGs in the separate relational-expression reduction.
[Boundary PR #29](https://github.com/Noelo-Lab/rust-joern/pull/29) ·
[Lexer PR #37](https://github.com/Noelo-Lab/rust-joern/pull/37)

Replaying the additional 69 frozen TUs gives 74 TUs and 3,354 requested
functions across both populations. Relative to #29, adding #37 raises
compatibility-mode body CFGs from 1,720 to 2,218 and original topology matches
from 1,322 to 1,792. The default mode retains all prior aligned CFGs and
topology matches as well. The six XGBoost bodies implicated in the lexer-only
probe remain aligned and match original Joern on both the prerequisite and
stacked builds. The FlatBuffers pair recovers 50 body CFGs, with ten original
body CFGs still missing. Results from the raw 1,000-repository run keep their
own denominator.

The checked builds are upstream main `6b85a04`, #29 `c2fae51`, and the
stacked #37 commit `5e185aa`. Every prepared-input and function-inventory
hash is verified against the captures. The stacked build passed 286 Rust
tests, 163 Python tests with 20 skips, formatting and Clippy. The machine
report preserves the five new per-TU counts, compiler and object hashes,
and the overall results. Complete graph captures and per-function outcomes
are retained locally under `workspace/benchmark-build-context-2026-11-19/`.
[Evidence summary](benchmark-build-context-2026-11-19.json)
