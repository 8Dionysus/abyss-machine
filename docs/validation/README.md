# Validation

Validation starts with the manifest-backed source-fast lane:

```bash
python scripts/ci_gate.py --mode source-fast
```

Host-contract tests exist for development and migration, but they are separate
from the public install smoke lane.
