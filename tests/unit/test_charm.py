# Copyright 2021 Cory Johns
# See LICENSE file for licensing details.

import pytest
from ops.model import ActiveStatus, BlockedStatus
from ops.testing import Harness
from charm import KubeStateMetricsOperator
from interface_prometheus.operator import PrometheusScrapeTarget


@pytest.fixture
def harness():
    harness = Harness(KubeStateMetricsOperator)
    try:
        yield harness
    finally:
        harness.cleanup()


@pytest.fixture(autouse=True)
def patch_get_hostname(monkeypatch):
    monkeypatch.setattr(PrometheusScrapeTarget, "get_hostname", lambda s: "ksm")


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


def test_register_metrics(harness):
    harness.begin()
    rid = harness.add_relation("metrics", "prometheus")
    rel = harness.model.get_relation("metrics", rid)
    harness.add_relation_unit(rid, "prometheus/0")
    assert rel.data[harness.charm.unit] == {
        "hostname": "ksm",
        "port": "8080",
        "metrics_path": "/proxy/metrics",
        "scrape_interval": "30s",
        "scrape_timeout": "15s",
        "labels": '{"kube-state-metrics": "metrics"}',
    }


def test_register_telemetry(harness):
    harness.begin()
    rid = harness.add_relation("telemetry", "prometheus")
    rel = harness.model.get_relation("telemetry", rid)
    harness.add_relation_unit(rid, "prometheus/0")
    assert rel.data[harness.charm.unit] == {
        "hostname": "ksm",
        "port": "8081",
        "metrics_path": "/proxy/metrics",
        "scrape_interval": "30s",
        "scrape_timeout": "15s",
        "labels": '{"kube-state-metrics": "telemetry"}',
    }
