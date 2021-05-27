# Copyright 2021 Cory Johns
# See LICENSE file for licensing details.

import pytest
from ops.model import ActiveStatus, BlockedStatus
from ops.testing import Harness
from charm import KubeStateMetricsOperator


@pytest.fixture
def harness():
    harness = Harness(KubeStateMetricsOperator)
    try:
        yield harness
    finally:
        harness.cleanup()


def test_config_changed(harness):
    harness.begin()

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

    # confirm conflicting config is blocked
    harness.update_config(
        {
            "metric-denylist": "foo",
        }
    )
    assert isinstance(harness.charm.unit.status, BlockedStatus)
