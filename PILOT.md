# Initial acquisition and strict parser smoke

2026-10-27: One input each from double-conversion, Ninja, Snappy and zlib was fetched with manifest verification and passed to local Rust-Joern release executable (20-second per-input timeout). All four returned nonzero under strict parsing. The three C++ inputs report unsupported syntax or CFG constructs in full preprocessed translation units; the unpreprocessed zlib input reports unexpanded macros. This is a pipeline smoke, not a support rate, a Joern comparison, or proof that the inputs are invalid.

No full corpus run, original Joern differential, standard-version qualification, expected-function inventory or CFG semantic validation has yet been performed.
