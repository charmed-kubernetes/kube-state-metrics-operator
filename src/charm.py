#!/usr/bin/env python3
# Copyright 2021 Cory Johns
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging

from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus
from ops.pebble import Layer

from interface_prometheus.operator import PrometheusScrapeTarget

logger = logging.getLogger(__name__)


class KubeStateMetricsOperator(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.metrics = PrometheusScrapeTarget(self, "metrics")
        self.telemetry = PrometheusScrapeTarget(self, "telemetry")
        self.framework.observe(self.on.config_changed, self._manage_workload)
        self.framework.observe(self.on.upgrade_charm, self._manage_workload)
        self.framework.observe(self.on.metrics_relation_joined, self._register_metrics)
        self.framework.observe(
            self.on.telemetry_relation_joined, self._register_telemetry
        )

    def _manage_workload(self, _):
        """Manage the container using the Pebble API."""
        if not self._validate_config():
            return

        container = self.unit.get_container("kube-state-metrics")
        container.add_layer("kube-state-metrics", self.layer, combine=True)
        if container.get_service("kube-state-metrics").is_running():
            container.stop("kube-state-metrics")
        container.start("kube-state-metrics")
        self.unit.status = ActiveStatus()

    def _register_metrics(self, _):
        self.metrics.expose_scrape_target(
            8080,
            "/proxy/metrics",
            scrape_interval="30s",
            scrape_timeout="15s",
            labels={"kube-state-metrics": "metrics"},
        )

    def _register_telemetry(self, _):
        self.telemetry.expose_scrape_target(
            8081,
            "/proxy/metrics",
            scrape_interval="30s",
            scrape_timeout="15s",
            labels={"kube-state-metrics": "telemetry"},
        )

    def _validate_config(self):
        """Check that charm config settings are valid.

        If the charm config is not valid, will set the unit status to BlockedStatus and
        return False.
        """
        if self.config["metric-allowlist"] and self.config["metric-denylist"]:
            self.unit.status = BlockedStatus(
                "metric-allowlist and metric-denylist are mutually exclusive"
            )
            return False
        return True

    @property
    def layer(self):
        """Pebble layer for workload."""
        return Layer(
            {
                "summary": "kube-state-metrics layer",
                "description": "pebble config layer for kube-state-metrics",
                "services": {
                    "kube-state-metrics": {
                        "override": "replace",
                        "summary": "kube-state-metrics",
                        "command": (
                            "/kube-state-metrics --port=8080 --telemetry-port=8081 "
                            + " ".join(
                                [
                                    f"--{key}=value"
                                    for key, value in self.config.items()
                                    if value
                                ]
                            )
                        ),
                        "startup": "enabled",
                    }
                },
            }
        )


if __name__ == "__main__":
    main(KubeStateMetricsOperator)
