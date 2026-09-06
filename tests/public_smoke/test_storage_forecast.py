from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from abyss_machine import storage_forecast as subject


def sample(hour: int, gib: int, key: str = "dev-one") -> dict:
    return {"path": "/srv", "filesystem_key": key, "timestamp": hour * 3600,
            "available_to_user_bytes": gib * 1024**3}


def physical_sample(hour: int, available_gib: int, reserved_gib: int,
                    key: str = "dev-one") -> dict:
    row = sample(hour, available_gib, key)
    row["reserved_bytes"] = reserved_gib * 1024**3
    return row


def test_forecast_requires_elapsed_history_and_same_filesystem() -> None:
    current = sample(3, 10)
    assert subject.forecast([sample(2, 11)], current)["status"] == "insufficient_history"
    assert subject.forecast([sample(h, 20 - h, "replaced-device") for h in range(3)], current)["status"] == "insufficient_history"


def test_forecast_uses_available_bytes_and_exposes_both_headrooms() -> None:
    report = subject.forecast([sample(h, 13 - h) for h in range(3)], sample(3, 10))
    assert report["status"] == "depleting"
    assert report["hours_to_free_floor"] == 5
    assert report["hours_to_full"] == 10
    assert report["net_bytes_per_day"] == 24 * 1024**3
    assert report["forecast_basis"] == "legacy_available_to_user_missing_reserved_bytes"
    assert report["net_physical_free_consumption_bytes_per_day"] is None


def test_forecast_uses_physical_free_when_reserve_policy_shifts() -> None:
    samples = [
        physical_sample(0, 10, 5),
        physical_sample(1, 10, 4),
        physical_sample(2, 11, 3),
    ]
    report = subject.forecast(samples, physical_sample(3, 11, 1))
    assert report["status"] == "depleting"
    assert report["forecast_basis"] == "physical_free_fixed_reserve"
    assert report["net_bytes_per_day"] == -8 * 1024**3
    assert report["net_physical_free_consumed_bytes"] == 3 * 1024**3
    assert report["net_physical_free_consumption_bytes_per_day"] == 24 * 1024**3
    assert report["reserve_shift_bytes"] == -4 * 1024**3
    assert report["physical_free_bytes"] == 12 * 1024**3
    assert report["hours_to_free_floor"] == 6
    assert report["hours_to_full"] == 11


def test_forecast_physical_free_control_keeps_cleanup_non_depleting() -> None:
    samples = [
        physical_sample(0, 10, 5),
        physical_sample(1, 11, 5),
        physical_sample(2, 12, 5),
    ]
    report = subject.forecast(samples, physical_sample(3, 13, 5))
    assert report["status"] == "not_depleting_in_observed_window"
    assert report["forecast_basis"] == "physical_free_fixed_reserve"
    assert report["net_physical_free_consumption_bytes_per_day"] == -24 * 1024**3
    assert report["reserve_shift_bytes"] == 0
    assert report["hours_to_free_floor"] is None


def test_forecast_does_not_invent_missing_reserved_bytes() -> None:
    samples = [physical_sample(0, 10, 5), sample(1, 10), sample(2, 10)]
    report = subject.forecast(samples, physical_sample(3, 10, 1))
    assert report["forecast_basis"] == "legacy_available_to_user_missing_reserved_bytes"
    assert report["net_physical_free_consumption_bytes_per_day"] is None
    assert report["reserve_shift_bytes"] is None


def test_cleanup_and_repeated_timestamp_do_not_manufacture_exhaustion() -> None:
    report = subject.forecast([sample(h, 10 + h) for h in range(3)], sample(3, 13))
    assert report["status"] == "not_depleting_in_observed_window"
    assert report["hours_to_full"] is None
    repeated = subject.forecast([sample(2, 15)] * 50, sample(3, 10))
    assert repeated["status"] == "insufficient_history"


def test_read_only_observation_never_creates_state_and_missing_mount_is_unknown(tmp_path: Path) -> None:
    state = tmp_path / "absent" / "capacity.json"
    report = subject.observe(state, paths=(tmp_path,), write=False)
    assert not state.exists() and not state.parent.exists()
    assert report["roots"][0]["status"] == "measurement_error"
    assert report["roots"][0]["available_to_user_bytes"] is None


def test_corrupt_history_is_preserved_and_reported(tmp_path: Path) -> None:
    state = tmp_path / "capacity.json"
    state.write_text("invalid")
    report = subject.observe(state, paths=(Path("/"),), write=True)
    assert report["status"] == "history_unavailable"
    assert state.read_text() == "invalid"
