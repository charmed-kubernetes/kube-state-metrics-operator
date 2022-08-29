import asyncio
import logging

import pytest

log = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test):
    ksm_charm = await ops_test.build_charm(".")

    # NB: We can't use a bundle for now
    # due to https://github.com/juju/python-libjuju/issues/506
    await ops_test.model.deploy(
        ksm_charm,
        config={"scrape-interval": "5s"},
        resources={
            "kube-state-metrics-image": "k8s.gcr.io/kube-state-metrics/kube-state-metrics:v2.0.0"  # noqa: E501
        },
        trust=True,  # so that the container can access k8s api
    )
    await ops_test.model.deploy("prometheus-k8s", channel="latest/beta", trust=True)
    await ops_test.model.add_relation("kube-state-metrics", "prometheus-k8s")
    await ops_test.model.wait_for_idle(wait_for_active=True)


async def test_stats_in_prometheus(ops_test, helpers):
    result = None
    for attempt in range(12):
        try:
            result = await helpers.query_prometheus(
                ops_test, 'count(kube_pod_status_phase{phase="Running"} > 0)'
            )
        except AssertionError:
            # Prometheus might not be up yet
            pass
            log.info("Waiting for Prometheus")
        else:
            assert result["status"] == "success"
            if result["data"]["result"]:
                break
        await asyncio.sleep(5)  # the scrape interval is 5s
    else:
        pytest.fail(f"Failed to get expected query result: {result}")
