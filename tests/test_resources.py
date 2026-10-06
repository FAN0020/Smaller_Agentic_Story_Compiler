"""Fail safely before loading weights, and protect independent studio processes."""

import pytest
from storycompiler.resources import ResourceError, Snapshot, check_capacity, inference_lease


def test_full_flux_is_rejected_on_24gb_even_when_idle():
    with pytest.raises(ResourceError, match="quantized"):
        check_capacity("black-forest-labs/FLUX.2-klein-4B", Snapshot(24, 20, 40, 0))


def test_low_disk_and_insufficient_headroom_stop_before_inference():
    with pytest.raises(ResourceError, match="disk"):
        check_capacity("stabilityai/sd-turbo", Snapshot(24, 12, 5, 0))
    with pytest.raises(ResourceError, match="available"):
        check_capacity("stabilityai/sd-turbo", Snapshot(24, 5, 40, 0))
    assert check_capacity("stabilityai/sd-turbo", Snapshot(24, 12, 40, 0)) == 4


def test_independent_inference_lease_releases_after_failure(tmp_path):
    path = tmp_path / "inference.lock"
    with pytest.raises(ValueError), inference_lease(path):
        with pytest.raises(ResourceError, match="already running"), inference_lease(path):
            pytest.fail("Acquired an occupied lease")
        raise ValueError("Interrupted inference")
    with inference_lease(path):
        pass
