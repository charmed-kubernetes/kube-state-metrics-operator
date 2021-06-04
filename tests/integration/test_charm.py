import logging

import pytest

log = logging.getLogger(__name__)


BUNDLE = """
series: kubernetes
applications:
  kube-state-metrics:
      charm: {{ kube_state_metrics }}
      scale: 1
      resources:
        kube-state-metrics-image: "k8s.gcr.io/kube-state-metrics/kube-state-metrics:v2.0.0"
  prometheus:
      charm: {{ prometheus }}
      scale: 1
      resources:
        prometheus-image: "prom/prometheus"
relations:
  - [kube-state-metrics, prometheus]
""".strip()


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test, helpers):
    # Fetch Prometheus charm.  NB: We have to use the repo for now to get the
    # updated sidecar version.
    prometheus_charm = await helpers.fetch_charm_src_from_github(
        ops_test.tmp_path,
        "canonical/prometheus-operator",
        branch="master",
    )

    await ops_test.model.deploy(
        ops_test.render_bundle(
            BUNDLE,
            kube_state_metrics=await ops_test.build_charm("."),
            prometheus=await ops_test.build_charm(prometheus_charm),
        )
    )
    await ops_test.model.wait_for_idle(
        apps=["kube-state-metrics", "prometheus"], wait_for_active=True
    )


async def test_stats_in_prometheus(ops_test, helpers):
    result = await helpers.query_prometheus(
        ops_test, 'count(kube_pod_status_phase{phase="Running"} > 0)'
    )
    assert result["status"] == "success"
    assert result["data"]["result"] != []
    assert int(result["data"]["result"][0]["value"][1]) > 0
