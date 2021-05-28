# Copyright 2021 Cory Johns
# See LICENSE file for licensing details.

import pytest
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
from ops.testing import Harness
from charm import KubeStateMetricsOperator


@pytest.fixture
def harness():
    harness = Harness(KubeStateMetricsOperator)
    try:
        yield harness
    finally:
        harness.cleanup()


def test_wait_for_ready(harness):
    harness.begin()
    assert isinstance(harness.charm.unit.status, MaintenanceStatus)
    # This hasn't been released yet
    # harness.container_pebble_ready("kube-state-metrics")
    # assert isinstance(harness.charm.unit.status, ActiveStatus)


def test_valid_config(harness):
    harness.begin()
    harness.charm._stored.pebble_ready = True

    # confirm valid config is accepted
    harness.update_config(
        {
            "metric-allowlist": "foo",
            "metric-labels-allowlist": "foo",
            "namespaces": "foo",
            "resources": "foo",
        }
    )
    assert isinstance(harness.charm.unit.status, ActiveStatus)


def test_invalid_config(harness):
    harness.begin()
    harness.charm._stored.pebble_ready = True

    # confirm conflicting config is blocked
    harness.update_config(
        {
            "metric-allowlist": "foo",
            "metric-denylist": "foo",
        }
    )
    assert isinstance(harness.charm.unit.status, BlockedStatus)
