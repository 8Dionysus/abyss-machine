from contextlib import nullcontext

from abyss_machine import artifact_subject_retention as retention


def test_materialization_only_retains_after_success_with_current_store_protected(monkeypatch, tmp_path):
    registry = tmp_path / 'registry'
    store = tmp_path / 'subjects' / 'current'
    monkeypatch.setattr(retention, 'configured_policy', lambda: {
        'enabled': True, 'registry_dir': str(registry),
    })
    monkeypatch.setattr(retention, 'maintenance_lock', lambda path: nullcontext())
    calls = []
    monkeypatch.setattr(retention, 'run', lambda *args, **kwargs: calls.append(kwargs) or {'ok': True})

    @retention.materialize_with_retention
    def materialize(bundle_dir, **kwargs):
        return {'ok': bundle_dir == 'success', 'store_dir': str(store)}

    assert materialize('failure', registry_dir=registry)['ok'] is False
    assert calls == []
    result = materialize('success', registry_dir=registry)
    assert result['subject_retention']['ok'] is True
    assert calls[0]['extra_protected'] == [str(store)]
    assert calls[0]['lock_held'] is True


def test_disabled_retention_never_invokes_cleanup(monkeypatch, tmp_path):
    monkeypatch.setattr(retention, 'configured_policy', lambda: {'enabled': False})
    monkeypatch.setattr(retention, 'run', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('cleanup called')))

    @retention.materialize_with_retention
    def materialize(bundle_dir, **kwargs):
        return {'ok': True}

    assert materialize('fixture', registry_dir=tmp_path) == {'ok': True}


def test_isolated_consumer_does_not_trigger_ambient_retention(monkeypatch, tmp_path):
    registry = tmp_path / 'registry'
    monkeypatch.setenv('ABYSS_MACHINE_ARTIFACT_SUBJECT_STORE_ISOLATED_ROOT', str(tmp_path / 'isolated'))
    monkeypatch.setattr(retention, 'configured_policy', lambda: {'enabled': True, 'registry_dir': str(registry)})
    monkeypatch.setattr(retention, 'run', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('ambient cleanup called')))

    @retention.materialize_with_retention
    def materialize(bundle_dir, **kwargs):
        return {'ok': True}

    assert materialize('fixture', registry_dir=registry) == {'ok': True}
