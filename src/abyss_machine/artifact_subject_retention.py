"""Bounded retention of completed host installation payloads, never source work.

Registry records, signatures and subject inventories remain. Only verified files
inside an obsolete subject store are retired. Current native selections, one
previous completed version, unfinished records and live references are protected.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
import datetime as dt
import fcntl
from functools import wraps
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import stat
import subprocess

FINISHED = {'release-ready', 'published', 'superseded', 'deprecated'}


def configured_policy():
    path = Path(os.environ.get('ABYSS_MACHINE_ETC_ROOT', '/etc/abyss-machine')) / 'storage-policy.json'
    try:
        return json.loads(path.read_text()).get('artifact_subject_retention', {})
    except (OSError, ValueError):
        return {}


def applies(policy, registry_dir):
    return policy.get('enabled') is True and Path(registry_dir).resolve() == Path(policy['registry_dir']).resolve()


@contextmanager
def maintenance_lock(registry_dir):
    path = Path(registry_dir) / '.subject-retention.lock'
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o664)
    try:
        if os.fstat(fd).st_uid == os.geteuid():
            os.fchmod(fd, 0o664)
            os.fchown(fd, -1, Path(registry_dir).stat().st_gid)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def serialized_registry_write(fn):
    @wraps(fn)
    def wrapped(bundle_dir, registry_dir, **kwargs):
        policy = configured_policy()
        with maintenance_lock(registry_dir) if applies(policy, registry_dir) else nullcontext():
            return fn(bundle_dir, registry_dir, **kwargs)
    return wrapped


def materialize_with_retention(fn):
    @wraps(fn)
    def wrapped(bundle_dir, **kwargs):
        policy = configured_policy()
        registry_dir = kwargs.get('registry_dir')
        if registry_dir is None or not applies(policy, registry_dir):
            return fn(bundle_dir, **kwargs)
        with maintenance_lock(registry_dir):
            result = fn(bundle_dir, **kwargs)
            if result.get('ok'):
                try:
                    result['subject_retention'] = run(
                        registry_dir, policy=policy, apply=True, lock_held=True,
                        extra_protected=[str(result['store_dir'])],
                    )
                except (OSError, ValueError) as exc:
                    result['subject_retention'] = {'ok': False, 'error': str(exc)}
            return result
    return wrapped


def reference_hits(stores, config_roots):
    """Return exact store references, without recording command lines or contents."""
    hits = {str(p): [] for p in stores}
    def inspect(value, label):
        for path in hits:
            if path in value:
                hits[path].append(label)
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            inspect((proc / 'cmdline').read_bytes().decode(errors='replace'), 'pid:' + proc.name)
            for leaf in ['exe', 'cwd']:
                try:
                    inspect(os.readlink(proc / leaf), 'pid:' + proc.name)
                except OSError:
                    pass
            for fd in (proc / 'fd').iterdir():
                try:
                    inspect(os.readlink(fd), 'pid:' + proc.name)
                except OSError:
                    pass
            for line in (proc / 'maps').read_text().splitlines():
                if '/' in line:
                    inspect(line, 'pid:' + proc.name)
        except OSError:
            pass
    for root in map(Path, config_roots):
        files = [root] if root.is_file() else root.rglob('*') if root.is_dir() else []
        for p in files:
            try:
                if p.is_symlink():
                    inspect(str(p.resolve()), 'symlink:' + str(p))
                elif p.is_file() and p.suffix in {'.json', '.toml', '.conf', '.service', '.timer', '.socket', '.env', '.sh', '.md'}:
                    # Markdown is included only in the active change ledger, never historical docs.
                    if p.suffix != '.md' or '/changes/active/' in str(p):
                        inspect(p.read_text(errors='replace'), 'config:' + str(p))
            except OSError:
                continue
    return {k: sorted(set(v)) for k, v in hits.items()}


def completion_proof(record, policy, cache):
    if not record.get('verification_ok'):
        return None
    state = record.get('lifecycle_state')
    if state in FINISHED:
        return {'basis': 'completed_release_lifecycle', 'state': state}
    if state != 'manually-verified':
        return None
    repo = policy.get('source_repo_roots', {}).get(record.get('source_repo'))
    commit = str(record.get('source_ref') or '')
    if not repo or not re.fullmatch('[0-9a-f]{40,64}', commit):
        return None
    key = (repo, commit)
    if key not in cache:
        prefix = []
        try:
            uid = Path(repo).stat().st_uid
            if os.geteuid() == 0 and uid != 0:
                prefix = ['/usr/sbin/runuser', '--user', pwd.getpwuid(uid).pw_name, '--']
        except OSError:
            cache[key] = None
            return None
        main = subprocess.run([*prefix, 'git', '-C', repo, 'rev-parse', '--verify', 'refs/heads/main'], capture_output=True, text=True)
        proof = None
        if main.returncode == 0:
            head = main.stdout.strip()
            result = subprocess.run([*prefix, 'git', '-C', repo, 'merge-base', '--is-ancestor', commit, head], capture_output=True, text=True)
            if result.returncode == 0:
                proof = {'basis': 'source_commit_already_in_main', 'repo': repo, 'commit': commit, 'main': head}
        cache[key] = proof
    return cache[key]


def build_plan(registry_dir, policy, *, extra_protected=(), check_references=True):
    from . import artifact_bundles as owner
    registry = owner.read_bundle_registry(registry_dir)
    records = registry['records']
    allowed = set(policy.get('artifact_classes', []))
    protected_digests = set()
    protection = {}
    def protect(digest, reason):
        protected_digests.add(digest)
        protection.setdefault(digest, []).append(reason)
    protected_paths = set(map(str, extra_protected))
    for record in list(registry['latest_by_artifact_class'].values()) + [r for rows in registry['latest_by_artifact_class_and_source_repo'].values() for r in rows.values()]:
        protect(str(record.get('artifact_subjects_digest') or ''), 'selected_current:' + str(record.get('record_id')))
        protected_paths.add(str(record.get('artifact_subject_store', {}).get('path') or ''))
    groups = {}
    by_digest = {}
    completions, completion_cache = {}, {}
    for r in records:
        digest = str(r.get('artifact_subjects_digest') or '')
        by_digest.setdefault((r.get('artifact_class'), digest), []).append(r)
        proof = completion_proof(r, policy, completion_cache)
        completions[r.get('record_id')] = proof
        if proof is None:
            protect(digest, 'completion_not_proven:' + str(r.get('lifecycle_state')) + ':' + str(r.get('source_ref')))
        elif r.get('artifact_class') in allowed:
            route = r.get('contract_surface_id') or Path(str(r.get('bundle_manifest_ref') or '')).name
            groups.setdefault((r.get('artifact_class'), r.get('source_repo'), route), []).append(r)
    keep = max(2, int(policy.get('keep_completed_versions', 2)))
    for rows in groups.values():
        selected = max(rows, key=owner._latest_sort_key)
        selected_time = str(selected.get('created_at') or '')
        # A newer prepared release can coexist with an older published selection.
        # It is pending promotion, not an obsolete version to be removed by rank.
        for record in rows:
            created = str(record.get('created_at') or '')
            if not created or not selected_time or created > selected_time:
                protect(str(record.get('artifact_subjects_digest') or ''), 'prepared_after_selected_release_or_missing_version_time')
        seen = set()
        for r in sorted(rows, key=owner._latest_sort_key, reverse=True):
            digest = str(r.get('artifact_subjects_digest') or '')
            if digest and digest not in seen:
                seen.add(digest)
                protect(digest, 'retained_route_version_' + str(len(seen)))
            if len(seen) >= keep:
                break
    stores = []
    for root in map(Path, policy.get('store_roots', [])):
        if root.resolve() != root or root.is_symlink() or not root.is_dir():
            continue
        for cls in sorted(allowed):
            parent = root / cls
            if parent.is_symlink() or not parent.is_dir():
                continue
            stores.extend(p for p in parent.iterdir() if p.is_dir() and not p.is_symlink())
    refs = reference_hits(stores, policy.get('live_reference_roots', [])) if check_references else {}
    candidates, retained = [], []
    for store in sorted(stores):
        path = str(store)
        try:
            meta_path = store / owner.ARTIFACT_SUBJECT_STORE_META
            if meta_path.is_symlink() or not meta_path.is_file() or meta_path.stat().st_nlink != 1:
                raise ValueError('subject inventory is missing or not a regular file')
            meta = json.loads(meta_path.read_text())
            cls = meta.get('artifact_class')
            digest = str(meta.get('aggregate_digest') or '')
            rs = by_digest.get((cls, digest), [])
            if owner._stable_digest(meta.get('files', [])) != digest:
                raise ValueError('subject inventory aggregate differs from its registered digest')
            for r in rs:
                rid = str(r.get('record_id') or '')
                rp = owner._registry_record_path(Path(registry_dir), rid)
                if not re.fullmatch('sha256:[0-9a-f]{64}', rid) or rp.resolve() != rp or not rp.is_file() or rp.stat().st_nlink != 1:
                    raise ValueError('unsafe registry record path')
            reason = None
            if meta.get('payload_disposition', {}).get('state') == 'retired':
                reason = 'already_retired'
            elif cls not in allowed or meta.get('schema') != 'abyss_machine_artifact_subject_store_v1' or store.name != digest.removeprefix('sha256:'):
                reason = 'unrecognized_store_identity'
            elif digest in protected_digests or path in protected_paths:
                reason = 'current_rollback_or_unfinished_record'
            elif refs.get(path):
                reason = 'live_reference'
            elif not rs or not any(completions.get(r.get('record_id')) for r in rs):
                reason = 'no_completed_registry_version'
            elif not meta.get('owner_repo') or any(r.get('source_repo') != meta['owner_repo'] for r in rs):
                reason = 'owner_mismatch'
            if reason:
                retained.append({'path': path, 'reason': reason, 'protection': protection.get(digest, []), 'refs': refs.get(path, [])})
                continue
            expected, files = set(), []
            for item in meta.get('files', []):
                rel = PurePosixPath(str(item.get('path') or ''))
                if not str(rel) or rel.is_absolute() or '..' in rel.parts or any(x in {'.codex', '.aoa', 'sessions', 'transcripts', 'captures'} for x in rel.parts):
                    raise ValueError('unsafe or protected payload path')
                p = store.joinpath(*rel.parts)
                if p.resolve() != p or not p.is_file():
                    raise ValueError('payload missing or contains symlink')
                s = p.stat()
                if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
                    raise ValueError('payload is not an independent regular file')
                expected.add(str(p))
                files.append({'path': str(p), 'size': s.st_size, 'allocated': s.st_blocks * 512, 'inode': s.st_ino, 'device': s.st_dev, 'mtime_ns': s.st_mtime_ns, 'sha256': str(item.get('sha256') or '').removeprefix('sha256:')})
            actual = {str(p) for p in store.rglob('*') if p.is_file() and p != meta_path}
            if actual != expected or not files or any(p.is_symlink() for p in store.rglob('*')):
                raise ValueError('store has unlisted files or no verified payload')
            ms = meta_path.stat()
            candidates.append({'path': path, 'artifact_class': cls, 'digest': digest, 'files': files, 'metadata_sha256': hashlib.sha256(meta_path.read_bytes()).hexdigest(), 'record_ids': [r['record_id'] for r in rs], 'completion_proofs': [completions[r['record_id']] for r in rs], 'reason': 'completed_version_replaced_by_current_and_retained_rollback'})
        except (OSError, ValueError, KeyError) as exc:
            retained.append({'path': path, 'reason': 'unclassified_store', 'error': str(exc)})
    return {'ok': True, 'schema': 'abyss_machine_artifact_subject_retention_plan_v1', 'registry_dir': str(registry_dir), 'candidates': candidates, 'retained': retained, 'latest_record_ids': {k: r['record_id'] for k, r in registry['latest_by_artifact_class'].items()}, 'summary': {'candidate_stores': len(candidates), 'payload_files': sum(len(x['files']) for x in candidates), 'allocated_bytes': sum(f['allocated'] for x in candidates for f in x['files'])}}


def run(registry_dir, *, policy=None, apply=False, extra_protected=(), lock_held=False):
    from . import artifact_bundles as owner
    policy = configured_policy() if policy is None else policy
    if not applies(policy, registry_dir):
        return {'ok': True, 'decision': 'policy_not_applicable', 'deleted_payload_files': 0}
    with nullcontext() if lock_held else maintenance_lock(registry_dir):
        plan = build_plan(registry_dir, policy, extra_protected=extra_protected)
        if not apply:
            return plan
        deleted, skipped = [], []
        for row in plan['candidates']:
            store = Path(row['path'])
            meta_path = store / owner.ARTIFACT_SUBJECT_STORE_META
            try:
                if hashlib.sha256(meta_path.read_bytes()).hexdigest() != row['metadata_sha256']:
                    raise ValueError('subject inventory changed')
                for f in row['files']:
                    p = Path(f['path']); s = p.lstat()
                    if p.resolve() != p or not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns) != (f['device'], f['inode'], f['size'], f['mtime_ns']):
                        raise ValueError('payload changed since planning')
                    if owner._file_digest(p).removeprefix('sha256:') != f['sha256']:
                        raise ValueError('payload digest differs from registered source')
                if ({str(p) for p in store.rglob('*') if p.is_file() and p != meta_path}
                        != {f['path'] for f in row['files']} or any(p.is_symlink() for p in store.rglob('*'))):
                    raise ValueError('store inventory changed during verification')
                # All files in this completed version verified before the first unlink.
                for f in row['files']:
                    Path(f['path']).unlink()
                meta = json.loads(meta_path.read_text())
                meta['payload_disposition'] = {'state': 'retired', 'at': dt.datetime.now(dt.timezone.utc).isoformat(), 'reason': row['reason'], 'archive_created': False, 'retained_current_record_ids': plan['latest_record_ids']}
                owner._write_json(meta_path, meta)
                for rid in row['record_ids']:
                    rp = owner._registry_record_path(Path(registry_dir), rid)
                    record = owner._read_json(rp)
                    status = dict(record.get('artifact_subject_store') or {})
                    if Path(str(status.get('path') or '')).resolve() == store.resolve():
                        status.update(ok=False, materialization_state='retired', retention_receipt=str(meta_path))
                        record['artifact_subject_store'] = status
                        owner._write_json(rp, record)
                deleted.append({'path': str(store), 'files': len(row['files']), 'allocated_bytes': sum(f['allocated'] for f in row['files']), 'digest': row['digest'], 'reason': row['reason']})
            except (OSError, ValueError, KeyError) as exc:
                skipped.append({'path': str(store), 'error': str(exc)})
        registry = owner.read_bundle_registry(registry_dir)
        owner._write_json(Path(registry_dir) / owner.BUNDLE_REGISTRY_INDEX, registry)
        if {k: r['record_id'] for k, r in registry['latest_by_artifact_class'].items()} != plan['latest_record_ids']:
            raise RuntimeError('retention unexpectedly changed registry selection')
        return {'ok': not skipped, 'schema': 'abyss_machine_artifact_subject_retention_apply_v1', 'deleted': deleted, 'skipped': skipped, 'deleted_payload_files': sum(x['files'] for x in deleted), 'allocated_bytes_removed': sum(x['allocated_bytes'] for x in deleted), 'retained': plan['retained'], 'archive_created': False, 'latest_record_ids_unchanged': True}
