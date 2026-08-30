# Provenance

This package follows the host storage policy that keeps `/` small and large
mutable AI/runtime artifacts under `/srv/abyss-machine`.

C19 references the existing storage write-preflight and machine-owned target
classes. It does not add a target root, execute a write, or permit host
automation to cross into project, stack, work, or game roots.

The managed-workspace lifecycle is created only by an explicit common launcher
request. Its release authority comes from the registered owner callback, not
from the storage candidate classifier, path names, age, pressure, or missing
processes. Existing and unmanaged data retain their prior owner boundaries.
