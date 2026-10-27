# Cross-platform source-CFG smoke — 2026-10-27

The same pinned Zlib `compress.c` source was separately compiled and preprocessed in six C11 profiles. These are six distinct prepared inputs, not the same bytes across targets. Per profile, Rust-Joern and original PyJoern 4.0.150.4 / Joern 4.0.150 received identical prepared bytes. An actual relocatable object was built and its format and machine checked, including an independent `file` inspection.

| Target | Compiler | Object | Source-owned observed candidates | Same directed topology and entry/exit roles | Missing exit, unqualified |
| --- | --- | --- | ---: | ---: | ---: |
| macOS arm64 | Clang 22.1.8 | Mach-O arm64 | 3 | 2 | 1 |
| macOS x86-64 | Clang 22.1.8, explicit Xcode macOS SDK | Mach-O x86-64 | 3 | 2 | 1 |
| Linux AArch64 | GCC 14.2.0 / musl | ELF AArch64 | 3 | 2 | 1 |
| Linux x86-64 | GCC 14.2.0 / musl | ELF x86-64 | 3 | 2 | 1 |
| Windows x86 | GCC 15.2.0 / MinGW | COFF x86 | 3 | 2 | 1 |
| Windows x86-64 | GCC 15.2.0 / MinGW | COFF x86-64 | 3 | 2 | 1 |

The object files are **relocatable cross-compiled objects**, not linked binaries or runtime execution. The Windows path uses MinGW, not MSVC, PDB or Windows-native execution. Each comparison concerns the same source input for the two backends within that target; it does not compare source CFG with binary CFG or assert equivalence between platform configurations. Function ownership is conservative line-marker evidence, not a proven complete project denominator. Missing exit markers are not adjudicated as tool defects. Matching topology alone does not prove semantic equivalence. The original capture is name-keyed and not safe for overload-sensitive population claims.

Windows x86-64 C++ was additionally tested with the pinned Snappy project, GNU C++11, CMake's compilation database and GCC/MinGW. Both `snappy.cc` and `snappy-sinksource.cc` compiled into verified x86-64 COFF objects and passed syntax checks. Rust-Joern strict rejected both preprocessed TUs; original Joern produced captures for the same hashes. This is not a per-function completeness or correctness score. CMake response-file content, generated headers, compilation database, prepared inputs and objects are hashed in the profile report.

Exact per-profile compiler/target/backend/object/graph hashes and observed status are in `platform-matrix-2026-10-27.json` and `snappy-windows-x64-2026-10-27.json`. Generated inputs, objects and raw captures remain in ignored local workspace, not distributed in the repository. Expanding the dataset requires project diversity, actual native toolchains/OS verification where needed, independently enumerated expected functions, overload-safe references, and semantics validation. No DecBench ranking or backend pin changed.
