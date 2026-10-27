# Joern C/C++ source corpus

An experimental, reproducible input inventory for evaluating C/C++ source parsing and CFG extraction. It is not a scored benchmark, a claim of C++ standard coverage, or a binary CFG dataset. Rust-Joern and original Joern must be compared on identical prepared bytes, options and expected-function populations; matching graph counts or parse success does not establish semantic equivalence.

## Seed population

`manifests/inputs.json` records 143 real upstream-derived source inputs:

* 135 preprocessed C++ translation units from [DecBench C++ raw corpus](https://huggingface.co/datasets/sjkim1127/decbench-cpp-raw-corpus), frozen at `f1b7e849641baf1d35e293f400bc36aa7a1a4e2c`: 99 Ninja, 24 double-conversion and 12 Snappy. Two additional pinned Ninja raw sources and two pinned Snappy raw sources support controlled C++ standard-mode experiments. The linked dataset's build summary records upstream revisions for Ninja and Snappy; double-conversion's upstream revision remains unverified. These counts are files, not independent functions or binaries. Optimization variants may duplicate source.
* Four unpreprocessed C source files from [zlib v1.3.1](https://github.com/madler/zlib/tree/51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf), pinned to `51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf`. They require project headers and compiler preprocessing for meaningful full-TU runs; the basic runner passes these raw files directly as diagnostic inputs only; the controlled preprocessing workflow below supplies project context.

The **original** C/C++ standard and exact compiler flags are unknown for every archived row until evidenced by original build commands. The preprocessing experiments below record their own explicitly selected modes; they do not reconstruct the historical builds. A preprocessed `.ii` does not by itself prove the standard or original configuration. These inputs are not balanced across C/C++ versions or projects. Binary-to-TU mappings, complete upstream licensing for the archived C++ files, build context, expected functions, held-out splits and full corpus qualification remain open work. No input-source contents are redistributed in this repository. zlib sources retain their original zlib license; use each upstream project's own license for its files. Do not assume the data inherit the scripts' license.

## Running

Requires Python 3.10+ and an existing Rust-Joern executable. This does not install or change either tool.

```sh
python3 scripts/corpus.py fetch --project snappy --limit 1
python3 scripts/corpus.py run --project snappy --limit 1 --binary /path/to/rust-joern --timeout 60
python3 -m unittest discover -s tests -v
```

The fetcher verifies pinned Git blob SHA-1 or SHA-256 and size. Input, graph and per-input results are under ignored `workspace/`. Records include input and backend hashes and explicit failure/timeout status. Resume reuses matching records and validates saved successful graph hashes. `--no-resume` reruns. `--strict` is always passed; `.ii` inputs additionally use `--preprocessed`. Graph production is recorded as `output`, not declared correct or complete. Raw source rejection is not a measure of the source's validity.

The next work is source-context collection, verified compiler/std provenance, original Joern differential runs with independent environments, expected-function and CFG topology/entry/exit validation, and semantic effect checks. Avoid using oracle source/debug facts to repair decompiler output when evaluating a producer.

## Controlled standard-mode experiment

The following checks out exact upstream commits and uses the local Clang and local system headers. It is a reproducible *profile*, not a claim to reproduce the original corpus build. Ninja requires at least C++17 in its checked-in CMake configuration.

```sh
git clone --no-checkout https://github.com/madler/zlib.git workspace/zlib-upstream
git -C workspace/zlib-upstream checkout --detach 51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf
python3 scripts/prepare_zlib.py --checkout workspace/zlib-upstream --compiler /path/to/clang --standard c11 --standard c17 --standard c23
python3 scripts/run_prepared.py --manifest workspace/prepared/manifest.json --binary /path/to/rust-joern

git clone --no-checkout https://github.com/ninja-build/ninja.git workspace/ninja-upstream
git -C workspace/ninja-upstream checkout --detach e4a128055f7698522da6de2821ffe0761623f298
python3 scripts/prepare_ninja.py --checkout workspace/ninja-upstream --compiler /path/to/clang++ --standard c++17 --standard c++20 --standard c++23
python3 scripts/run_prepared.py --manifest workspace/prepared-ninja/manifest.json --output-dir workspace/ninja-evaluation --binary /path/to/rust-joern
```

Preparation rejects dirty or wrong-revision checkouts, verifies source hashes, checks compiler syntax, and saves source, compiler, command and prepared-byte provenance. `-P` deliberately removes line markers: original-file ownership is therefore not established by this experiment. System header contents are captured in the prepared hash, not independently pinned. The two Ninja inputs were selected for a source-level experiment; they are not matched to a specific archived binary.

For unchanged original Joern, use Rust-Joern's `scripts/capture_pyjoern_corpus.py` and the generated `reference-manifest.json`, with an isolated original PyJoern 4.0.150.4 environment. That tool retains per-input timeout/error and prepared hash records. The `scripts/report_prepared.py` helper builds an evidence summary; it checks prepared hash identity but does not compare CFG topology or prove semantics. See [experiment notes](reports/README.md).

## Source ownership and CFG topology

Install `requirements.txt` in the comparison environment. `prepare_zlib.py` and `prepare_ninja.py` accept `--preserve-linemarkers --output-dir PATH`, preserving compiler line markers for source-owned function candidates. `scripts/compare_cfg.py --help` describes the hash-checked per-input comparison; it uses the prepared input, source file, native output and original reference, together with both native-result and preparation manifests. It checks exactly one entry, at least one exit, edge/node integrity, reachability, directed topology and entry/exit roles. Oversized graphs, duplicate edges, unbounded graphs and timeouts are explicitly unqualified. Equal topology does not establish equivalent statements or effects.

This is an **observed candidate** inventory, not a complete function denominator. The original capture format is name-keyed and may collapse duplicate names; it must be replaced with a collision-preserving identity contract before overload-sensitive C++ evaluation. Preprocessor markers identify source provenance only when the complete observed function span maps to the same exact source.

For C++11/14, `scripts/prepare_snappy.py` reads an explicitly selected CMake `compile_commands.json`, checks the pinned clean source revision, verifies source hashes and records compiler, configured standard, database, generated header and prepared-byte hashes. Build configuration is an experiment, not the historical archived corpus build. Example setup:

```sh
git clone --no-checkout https://github.com/google/snappy.git workspace/snappy-upstream
git -C workspace/snappy-upstream checkout --detach 2a6c78c781cb76ad191795449cb2267f33138150
cmake -S workspace/snappy-upstream -B workspace/snappy-build-c11 -DCMAKE_CXX_COMPILER=/path/to/clang++ -DCMAKE_CXX_STANDARD=11 -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DSNAPPY_BUILD_TESTS=OFF -DSNAPPY_BUILD_BENCHMARKS=OFF -DCMAKE_POLICY_VERSION_MINIMUM=3.5
python3 scripts/prepare_snappy.py --checkout workspace/snappy-upstream --database workspace/snappy-build-c11/compile_commands.json --output-dir workspace/snappy-gnu11
python3 scripts/run_prepared.py --manifest workspace/snappy-gnu11/manifest.json --output-dir workspace/snappy-gnu11-eval --binary /path/to/rust-joern
```

Repeat with a separate build directory and `-DCMAKE_CXX_STANDARD=14`. For a Linux AArch64 cross-compiler, choose explicit CMake system and compiler settings and keep the resulting target separate from native macOS. See [boundary experiment](reports/CFG-BOUNDARIES.md).
