# Controlled input experiment — 2026-10-27

Clang 22.1.8 on the local macOS host accepted four pinned zlib sources in each of C11, C17 and C23 and two pinned Ninja sources in C++17, C++20 and C++23. The exact compiler and prepared-byte hashes are in the JSON reports. These are newly chosen experimental flags, not evidence of original corpus flags or broad standards support.

Rust-Joern release binary (hash in each report) in strict mode returned graph output for all 12 zlib preparations and rejected all six Ninja preparations. It reported unsupported executable syntax in the preprocessed Ninja inputs, including included headers. These are TU-level results, not per-function completeness or correctness.

Original PyJoern 4.0.150.4 / Joern v4.0.150 captured all four zlib C11 inputs and both Ninja C++17 inputs in isolated processes with matching prepared SHA-256; remaining original captures were not run. The original outputs include system/project header declarations, so total function counts cannot be read as project-function coverage.

As an exploratory C11 check, `adler32`, `adler32_z`, `crc32`, `crc32_z`, `compress`, `compress2`, `uncompress` and `uncompress2` were present on both sides at the same prepared-file start line. Their CFG node/edge counts matched, but four nontrivial graphs (`adler32_z`, `crc32_z`, `compress2`, `uncompress2`) lacked an exit marker in both outputs. Equal counts do not establish topology or semantic equivalence; these graphs have not passed a bounded entry/exit gate. Raw graphs and logs are local ignored workspace artifacts, not part of this repository; their reference hashes are recorded for identifying the captures.

The preprocessing `-P` removes original file/line markers; project ownership, precise function denominator, semantic effects and release-level standards coverage are not validated. C++11/14, C-only project diversity, other compilers, all-original-reference runs and meaningful per-function CFG topology comparisons remain future work.
