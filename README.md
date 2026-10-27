# Joern C/C++ source corpus

An experimental, reproducible input inventory for evaluating C/C++ source parsing and CFG extraction. It is not a scored benchmark, a claim of C++ standard coverage, or a binary CFG dataset. Rust-Joern and original Joern must be compared on identical prepared bytes, options and expected-function populations; matching graph counts or parse success does not establish semantic equivalence.

## Seed population

`manifests/inputs.json` records 139 real upstream-derived source inputs:

* 135 preprocessed C++ translation units from [DecBench C++ raw corpus](https://huggingface.co/datasets/sjkim1127/decbench-cpp-raw-corpus), frozen at `f1b7e849641baf1d35e293f400bc36aa7a1a4e2c`: 99 Ninja, 24 double-conversion and 12 Snappy. The linked dataset's build summary records upstream revisions for Ninja and Snappy; double-conversion's upstream revision remains unverified. These counts are files, not independent functions or binaries. Optimization variants may duplicate source.
* Four unpreprocessed C source files from [zlib v1.3.1](https://github.com/madler/zlib/tree/51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf), pinned to `51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf`. They require project headers and compiler preprocessing for meaningful full-TU runs; the runner currently passes these raw files directly as diagnostic inputs only.

C/C++ standard and exact compiler flags are **unknown for every row** until evidenced by original build commands. A preprocessed `.ii` does not by itself prove the standard or original configuration. These inputs are not balanced across C/C++ versions or projects. Binary-to-TU mappings, complete upstream licensing for the archived C++ files, build context, expected functions, held-out splits and full corpus qualification remain open work. No input-source contents are redistributed in this repository. zlib sources retain their original zlib license; use each upstream project's own license for its files. Do not assume the data inherit the scripts' license.

## Running

Requires Python 3.10+ and an existing Rust-Joern executable. This does not install or change either tool.

```sh
python3 scripts/corpus.py fetch --project snappy --limit 1
python3 scripts/corpus.py run --project snappy --limit 1 --binary /path/to/rust-joern --timeout 60
python3 -m unittest discover -s tests -v
```

The fetcher verifies pinned Git blob SHA-1 or SHA-256 and size. Input, graph and per-input results are under ignored `workspace/`. Records include input and backend hashes and explicit failure/timeout status. Resume reuses matching records and validates saved successful graph hashes. `--no-resume` reruns. `--strict` is always passed; `.ii` inputs additionally use `--preprocessed`. Graph production is recorded as `output`, not declared correct or complete. Raw source rejection is not a measure of the source's validity.

The next work is source-context collection, verified compiler/std provenance, original Joern differential runs with independent environments, expected-function and CFG topology/entry/exit validation, and semantic effect checks. Avoid using oracle source/debug facts to repair decompiler output when evaluating a producer.
