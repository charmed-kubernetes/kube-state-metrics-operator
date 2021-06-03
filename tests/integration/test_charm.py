import logging

import pytest

log = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test, helpers):
    await ops_test.model.deploy(
        await ops_test.build_charm("."),
        resources={
            "kube-state-metrics-image": "k8s.gcr.io/kube-state-metrics/kube-state-metrics:v2.0.0"
        },
    )
    await ops_test.model.wait_for_idle(wait_for_active=True)

    # Add Prometheus (this is done separately so that we can at least verify
    # above that the kube-state-metrics charm successfully builds & deploys,
    # even if the Prometheus charm doesn't). NB: We have to use the repo for
    # now to get the updated sidecar version.
    prometheus_charm = await helpers.fetch_charm_src_from_github(
        ops_test.tmp_path,
        "canonical/prometheus-operator",
        branch="master",
    )

    await ops_test.model.deploy(
        await ops_test.build_charm(prometheus_charm),
        resources={
            "prometheus-image": "prom/prometheus",
        },
    )
    await ops_test.model.add_relation("kube-state-metrics", "prometheus-k8s")
    await ops_test.model.wait_for_idle(wait_for_active=True)


async def test_stats_in_prometheus(ops_test, helpers):
    result = await helpers.query_prometheus(
        ops_test, 'count(kube_pod_status_phase{phase="Running"} > 0)'
    )
    assert result["status"] == "success"
    assert result["data"]["result"] != []
    assert int(result["data"]["result"][0]["value"][1]) > 0
