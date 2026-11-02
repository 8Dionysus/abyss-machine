import json

from abyss_machine import cli


def configure_maps(monkeypatch, root):
    monkeypatch.setattr(cli, 'MAPS_ROOT', root)
    monkeypatch.setattr(cli, 'MAPS_LATEST_PATH', root / 'latest.json')
    monkeypatch.setattr(cli, 'MAPS_INDEX_PATH', root / 'index.json')
    monkeypatch.setattr(cli, 'MAPS_START_PATH', root / 'START.md')
    monkeypatch.setattr(cli, 'maps_axis_definitions', lambda: [{'axis': 'alpha', 'question': 'Fixture'}])
    monkeypatch.setattr(cli, 'maps_policy_document', lambda: {})
    monkeypatch.setattr(cli, 'maps_index_document', lambda data: {})
    monkeypatch.setattr(cli, 'maps_start_markdown', lambda data: 'start')
    monkeypatch.setattr(cli, 'maps_axis_index_markdown', lambda axis, entries: 'index')
    monkeypatch.setattr(cli, 'safe_append_jsonl', lambda *args: None)
    monkeypatch.setattr(cli, 'ai_daily_jsonl_path', lambda path: path / 'history.jsonl')


def card(identifier):
    return {'schema': f'{cli.SCHEMA_PREFIX}_maps_entry_v1', 'axis': 'alpha',
            'id': identifier, 'truth_status': 'generated_route_signal_not_source_truth'}


def test_publication_prunes_only_displaced_generated_cards(monkeypatch, tmp_path):
    root = tmp_path / 'maps'
    configure_maps(monkeypatch, root)
    entries = root / 'alpha' / 'entries'
    entries.mkdir(parents=True)
    old = entries / 'alpha:0000000000000001.json'
    old.write_text(json.dumps(card(old.stem)))
    foreign = entries / 'alpha:0000000000000002.json'
    foreign.write_text('{}')
    current = card('alpha:0000000000000003')

    assert cli.write_machine_maps_files({}, {'alpha': [current]}) == []
    assert not old.exists()
    assert foreign.read_text() == '{}'
    assert json.loads((entries / (current['id'] + '.json')).read_text()) == current


def test_failed_entry_write_does_not_prune_previous_card(monkeypatch, tmp_path):
    root = tmp_path / 'maps'
    configure_maps(monkeypatch, root)
    entries = root / 'alpha' / 'entries'
    entries.mkdir(parents=True)
    old = entries / 'alpha:0000000000000001.json'
    old.write_text(json.dumps(card(old.stem)))
    monkeypatch.setattr(cli, 'safe_atomic_write_json', lambda path, *args: {'path': str(path), 'error': 'fixture'})

    assert cli.write_machine_maps_files({}, {'alpha': [card('alpha:0000000000000003')]})
    assert old.is_file()
