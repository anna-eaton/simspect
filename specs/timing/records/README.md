# Timing records (retroactive)

Canonical timing-config for each gem5 campaign that has already run — extracted from its
`results/<campaign>/run_config.jsonc` on the container (provenance in each file's `_source`).
Same format as the `specs/timing/*.json` candidates and new-launch sweep configs: `build`,
`scheme`(+`scheme_name`), `fnc_commit_stall_cycles`, `branch_ann_enable`, `extra_args`, and a
`sweep` block (`resolve_stall_points`, `unresolved_stall`) for the swept knobs. Generated 2026-10-26.
