import json
import logging
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlretrieve
from zipfile import ZipFile

import pytest

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def helpers():
    return Helpers()


class Helpers:
    async def juju_run(self, unit, cmd):
        """Run a command on a unit and return the output."""
        action = await unit.run(cmd)
        result = await action.wait()
        code = result.results["return-code"]
        stdout = result.results.get("stdout")
        stderr = result.results.get("stderr")
        assert code == 0, f"{cmd} failed ({code}): {stderr or stdout}"
        return stdout

    async def fetch_charm_src_from_github(self, tmp_path, repo, branch="main"):
        """Fetch a charm source from GitHub."""
        url = f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"
        zip_file = tmp_path / f"{Path(repo).name}.zip"
        urlretrieve(url, zip_file)
        with ZipFile(zip_file) as zip:
            charm_dir = tmp_path / zip.namelist()[0]
            zip.extractall(tmp_path)

        # NB: ZipFile does not properly preserve permissions, so we have to restore the
        # exec bit on src/charm.py. See https://bugs.python.org/issue15795 and also
        # https://stackoverflow.com/questions/39296101/python-zipfile-removes-execute-permissions-from-binaries
        (charm_dir / "src/charm.py").chmod(0x775)

        return charm_dir

    async def query_prometheus(self, ops_test, query):
        prometheus_unit = ops_test.model.applications["prometheus-k8s"].units[0]
        # Query pods.
        query = {"query": query}
        qs = urlencode(query)
        url = f"http://localhost:9090/api/v1/query?{qs}"
        output = await self.juju_run(prometheus_unit, f"curl '{url}'")
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            log.error(f"Failed to parse query results: {output}")
            raise
