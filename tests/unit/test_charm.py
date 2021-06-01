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


@pytest.fixture(autouse=True)
def patch_address(monkeypatch):
    monkeypatch.setattr(
        KubeStateMetricsOperator, "monitoring_address", property(lambda s: "ksm")
    )


def test_valid_config(harness):
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


def test_invalid_config(harness):
    harness.begin()

    # confirm conflicting config is blocked
    harness.update_config(
        {
            "metric-allowlist": "foo",
            "metric-denylist": "foo",
        }
    )
    assert isinstance(harness.charm.unit.status, BlockedStatus)


def test_register_monitoring(harness):
    harness.set_leader(True)
    harness.begin()
    rid = harness.add_relation("monitoring", "prometheus")
    rel = harness.model.get_relation("monitoring", rid)
    harness.add_relation_unit(rid, "prometheus/0")
    assert rel.data[harness.charm.app] == {"targets": '["ksm:8080", "ksm:8081"]'}
