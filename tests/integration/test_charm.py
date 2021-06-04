import asyncio
import logging

import pytest

log = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test, helpers):
    ksm_charm = await ops_test.build_charm(".")
    # NB: We have to use the repo for Prometheus for now to get the updated
    # sidecar version.
    prometheus_charm = await ops_test.build_charm(
        await helpers.fetch_charm_src_from_github(
            ops_test.tmp_path,
            # Temporarily use branch on fork until
            # https://github.com/canonical/prometheus-operator/pull/40 lands.
            "johnsca/prometheus-operator",
            branch="gh/39/eschew-update-status",
            # "canonical/prometheus-operator",
            # branch="master",
        )
    )

    # NB: We can't use a bundle for now due to https://github.com/juju/python-libjuju/issues/506
    await ops_test.model.deploy(
        ksm_charm,
        resources={
            "kube-state-metrics-image": "k8s.gcr.io/kube-state-metrics/kube-state-metrics:v2.0.0"
        },
    )
    await ops_test.model.deploy(
        prometheus_charm,
        resources={
            "prometheus-image": "prom/prometheus",
        },
    )
    await ops_test.model.add_relation("kube-state-metrics", "prometheus-k8s")
    await ops_test.model.wait_for_idle(wait_for_active=True)


async def test_stats_in_prometheus(ops_test, helpers):
    result = None
    for attempt in range(3):
        try:
            result = await helpers.query_prometheus(
                ops_test, 'count(kube_pod_status_phase{phase="Running"} > 0)'
            )
        except AssertionError:
            # Prometheus might not be up yet
            pass
        else:
            assert result["status"] == "success"
            if result["data"]["result"]:
                break
        await asyncio.sleep(5)  # the scrape interval is 5s
    else:
        pytest.fail(f"Failed to get expected query result: {result}")
