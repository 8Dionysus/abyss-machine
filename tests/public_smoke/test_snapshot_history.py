import json

import pytest

from abyss_machine import snapshot_history


def test_snapshot_delta_round_trip_and_corrupt_base_fail_closed(tmp_path):
    path = tmp_path / 'snapshots.jsonl'
    first = {'schema': 'snapshot', 'text': 'a' * 8000, 'sequence': 1}
    second = {**first, 'sequence': 2}
    assert snapshot_history.append_snapshot(path, first)['delta'] is False
    assert snapshot_history.append_snapshot(path, second)['delta'] is True

    lines = path.read_bytes().splitlines()
    decoder = snapshot_history.Decoder()
    assert json.loads(decoder.decode(lines[0])) == first
    assert json.loads(decoder.decode(lines[1])) == second

    corrupted = json.loads(lines[1])
    corrupted['base_sha256'] = '0' * 64
    decoder = snapshot_history.Decoder()
    decoder.decode(lines[0])
    with pytest.raises(snapshot_history.HistoryError, match='base checksum'):
        decoder.decode(json.dumps(corrupted).encode())
