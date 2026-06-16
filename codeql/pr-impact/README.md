# PR Collision Atlas CodeQL Query Pack

This pack emits SARIF records with `pr_atlas:{...}` JSON payloads. The Python
runner parses those payloads into:

- `pr_codeql_changes` from `pr-impact/symbol-definitions`
- `static_impact_findings` from public surface and test relation queries

The analysis pipeline treats CodeQL as authoritative static evidence. If this
pack or the CodeQL CLI fails, the backend records a failed or partial snapshot
and falls back to deterministic PR/file/hunk risk.

If `codeql/python-all` is not present locally, install dependencies with:

```bash
codeql pack install
```
