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
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.pebble import Layer, ConnectionError

from charms.prometheus.v1.prometheus import PrometheusConsumer

logger = logging.getLogger(__name__)


class KubeStateMetricsOperator(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.monitoring = PrometheusConsumer(
            self, "monitoring", {"prometheus": ">=2.0"}
        )

        self.framework.observe(
            self.on.kube_state_metrics_pebble_ready, self._manage_workload
        )
        self.framework.observe(self.on.config_changed, self._manage_workload)
        self.framework.observe(self.on.upgrade_charm, self._manage_workload)
        self.framework.observe(
            self.on.monitoring_relation_created, self._register_monitoring
        )
        self.framework.observe(self.on.leader_elected, self._register_monitoring)

    def _manage_workload(self, _):
        """Manage the container using the Pebble API."""
        if not self._validate_config():
            return

        try:
            container = self.unit.get_container("kube-state-metrics")
            container.add_layer("kube-state-metrics", self.layer, combine=True)
            if container.get_service("kube-state-metrics").is_running():
                container.stop("kube-state-metrics")
            container.start("kube-state-metrics")
            self.unit.status = ActiveStatus()
        except ConnectionError:
            self.unit.status = WaitingStatus("Waiting for Pebble")

    def _register_monitoring(self, event):
        """Register with a monitoring provider."""
        # NB: We have to check the relation here because we might be in a pre-relation
        # leader-elected hook (and on the other hand, we might get the relation hook
        # while we are not the leader).
        if not (self.unit.is_leader() and self.model.get_relation("monitoring")):
            return
        address = self.monitoring_address
        if not address:
            # I don't think this should ever actually happen, and if it does, it
            # likely indicates a more serious issue, but we should handle and
            # report it gracefully anyway.
            self.unit.status = WaitingStatus("Waiting for ingress address")
            event.defer()
            return
        self.monitoring.add_endpoint(address, 8080)  # metrics
        self.monitoring.add_endpoint(address, 8081)  # telemetry

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
    def monitoring_address(self):
        binding = self.model.get_binding("monitoring")
        if not binding:
            return None
        return str(binding.network.ingress_address or binding.network.bind_address)

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
