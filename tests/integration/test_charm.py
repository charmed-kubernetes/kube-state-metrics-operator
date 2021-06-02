import json
import logging
from urllib.parse import urlencode
from urllib.request import urlretrieve
from zipfile import ZipFile

import pytest

log = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test):
    ksm = await ops_test.build_charm(".")
    # Temporarily work around https://bugs.launchpad.net/juju/+bug/1929076
    await juju_deploy(  # ops_test.model.deploy(
        ops_test,
        ksm,
        resources={
            "kube-state-metrics-image": "k8s.gcr.io/kube-state-metrics/kube-state-metrics:v2.0.0"
        },
    )
    await ops_test.model.wait_for_idle(wait_for_active=True)


@pytest.mark.abort_on_fail
async def test_add_prometheus(ops_test):
    # Have to use the repo for now because the version on Charmhub.io is out of date.
    prometheus_zip_file = ops_test.tmp_path / "prometheus-operator-master.zip"
    prometheus_charm_dir = ops_test.tmp_path / "prometheus-operator-master"
    urlretrieve(
        "https://github.com/canonical/prometheus-operator/archive/refs/heads/master.zip",
        prometheus_zip_file,
    )
    prometheus_charm_dir.mkdir()
    with ZipFile(prometheus_zip_file) as zip:
        zip.extractall(ops_test.tmp_path)
    # NB: ZipFile does not properly preserve permissions, so we have to restore the
    # exec bit on src/charm.py. See https://bugs.python.org/issue15795 and also
    # https://stackoverflow.com/questions/39296101/python-zipfile-removes-execute-permissions-from-binaries
    charm_file = prometheus_charm_dir / "src" / "charm.py"
    charm_file.chmod(0x775)

    # Deploy and relate.
    prometheus_charm_file = await ops_test.build_charm(prometheus_charm_dir)
    # Temporarily work around https://bugs.launchpad.net/juju/+bug/1929076
    await juju_deploy(  # ops_test.model.deploy(
        ops_test,
        prometheus_charm_file,
        resources={
            "prometheus-image": "prom/prometheus",
        },
    )
    await ops_test.model.add_relation("kube-state-metrics", "prometheus-k8s")
    await ops_test.model.wait_for_idle(wait_for_active=True)


async def test_stats_in_prometheus(ops_test):
    prometheus_unit = ops_test.model.applications["prometheus-k8s"].units[0]
    # Query pods.
    query = {"query": 'count(kube_pod_status_phase{phase="Running"} > 0)'}
    qs = urlencode(query)
    url = f"http://localhost:9090/api/v1/query?{qs}"
    output = await juju_run(prometheus_unit, f"curl '{url}'")
    try:
        result = json.loads(output)
    except json.JSONDecodeError:
        log.error(f"Failed to parse query results: {output}")
        raise
    assert result["status"] == "success"
    assert int(result["data"]["result"][0]["value"][1]) > 0


async def juju_deploy(ops_test, charm, resources=None):
    num_apps = len(ops_test.model.applications.keys())
    resource_args = []
    for res_name, res_value in (resources or {}).items():
        resource_args.extend(["--resource", f"{res_name}={res_value}"])
    log.info(f"Deploying charm from {charm} using CLI")
    rc, stdout, stderr = await ops_test.run(
        "juju",
        "deploy",
        "-m",
        ops_test.model_full_name,
        charm,
        *resource_args,
    )
    assert rc == 0, f"Failed to deploy {charm.name}: {stderr or stdout}"
    # CLI doesn't block until the app is actually visible, so we need to make sure
    # that it's visible in our view of the model before continuing.
    log.info("Waiting for application to be visible model")
    await ops_test.model.block_until(
        lambda: len(ops_test.model.applications.keys()) > num_apps
    )


async def juju_run(unit, cmd):
    result = await unit.run(cmd)
    code = result.results["Code"]
    stdout = result.results.get("Stdout")
    stderr = result.results.get("Stderr")
    assert code == "0", f"{cmd} failed ({code}): {stderr or stdout}"
    return stdout
