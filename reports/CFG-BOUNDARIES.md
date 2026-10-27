# Source ownership and CFG boundary experiment — 2026-10-27

The pinned Zlib sources were preprocessed with line markers under Clang 22.1.8 on macOS and GCC 14.2.0 targeting Linux AArch64/musl. Original PyJoern 4.0.150.4 / Joern 4.0.150 and the Rust-Joern release binary received the same hashed C11 prepared bytes per compiler. The exact input, compiler, backend and reference hashes are recorded in `cfg-ownership-2026-10-27.json` and the compiler-profile reports. Clang and GCC produced different preprocessed inputs and are **not** treated as a matched cross-compiler population.

| Profile | Observed source-owned candidates | Directed topology and entry/exit roles match | Unqualified: missing exit |
| --- | ---: | ---: | ---: |
| Clang/macOS | 20 | 15 | 5 |
| GCC/Linux AArch64 | 23 | 18 | 5 |

A match means directed graph isomorphism with entry/exit roles after rejecting invalid edges, missing boundaries and unreachable nodes. It does not compare statements, effects or semantic behavior. These are observed candidates, not a complete independently established function population. Original Joern capture is name-keyed and can collapse duplicate names, so this identity method is not qualified for C++ overloads. The missing exit marker is a fact about the current exports; its semantic cause has not been established. It is not treated as proof of a parser bug.

Snappy's pinned `CMakeLists.txt` declares C++11 minimum. The actual local CMake compilation database was used to build and preprocess two source TUs under Clang `gnu++11` and `gnu++14`, plus GCC `gnu++11` for Linux AArch64. All six preparations passed the respective compiler's syntax check. Original Joern captured all six exact inputs; Rust-Joern strict rejected all six. That is a TU-level result, with project and header code combined; original capture is not evidence of CFG correctness. Reports contain source, compiler, compilation-database, generated-header and prepared-byte hashes. GNU extensions and target/compiler differences remain explicit; these tests do not prove ISO C++11/14 or full-version support.

The original and native raw graph captures are retained only under the ignored local workspace. No DecBench metric, denominator, public leaderboard or backend pin changed. Future work: compiler-AST-backed complete expected function inventory, original reference format with overload-safe identities, missing-exit semantic investigation, C++ project-owned CFG comparison and independently validated statement/effect parity.
