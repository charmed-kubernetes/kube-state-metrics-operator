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
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus

logger = logging.getLogger(__name__)


class KubeStateMetricsOperator(CharmBase):
    """Charm the service."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(
            self.on.kube_state_metrics_pebble_ready,
            self._on_kube_state_metrics_pebble_ready,
        )
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self._stored.set_default(things=[])

    def _on_kube_state_metrics_pebble_ready(self, event):
        """Define and start a workload using the Pebble API.

        TEMPLATE-TODO: change this example to suit your needs.
        You'll need to specify the right entrypoint and environment
        configuration for your specific workload. Tip: you can see the
        standard entrypoint of an existing container using docker inspect

        Learn more about Pebble layers at https://github.com/canonical/pebble
        """
        # Get a reference the container attribute on the PebbleReadyEvent
        container = event.workload
        # Define an initial Pebble layer configuration
        pebble_layer = {
            "summary": "kube-state-metrics layer",
            "description": "pebble config layer for kube-state-metrics",
            "services": {
                "kube-state-metrics": {
                    "override": "replace",
                    "summary": "kube-state-metrics",
                    "command": "gunicorn -b 0.0.0.0:80 kube-state-metrics:app -k gevent",
                    "startup": "enabled",
                    "environment": {"thing": self.model.config["thing"]},
                }
            },
        }
        # Add intial Pebble config layer using the Pebble API
        container.add_layer("kube-state-metrics", pebble_layer, combine=True)
        # Autostart any services that were defined with startup: enabled
        container.autostart()
        # Learn more about statuses in the SDK docs:
        # https://juju.is/docs/sdk/constructs#heading--statuses
        self.unit.status = ActiveStatus()

    def _on_config_changed(self, _):
        """Enforce valid config and update service if needed."""
        if self.config["metric-allowlist"] and self.config["metric-denylist"]:
            self.unit.status = BlockedStatus(
                "metric-allowlist and metric-denylist are mutually exclusive"
            )
        else:
            self.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(KubeStateMetricsOperator)
