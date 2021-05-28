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
from ops.model import ActiveStatus, BlockedStatus, ModelError
from ops.pebble import Layer

logger = logging.getLogger(__name__)


class InvalidConfigError(ValueError):
    pass


class KubeStateMetricsOperator(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._manage_workload)

    def _manage_workload(self, _):
        """Manage the container using the Pebble API."""
        try:
            self._validate_config()
        except InvalidConfigError as e:
            self.unit.status = BlockedStatus(str(e))
            return

        container = self.unit.get_container(self.name)
        layer_svc = self.layer.services.get(self.name)
        plan_svc = container.get_plan().services.get(self.name)
        if not plan_svc or plan_svc.command != layer_svc.command:
            container.add_layer(self.name, self.layer, combine=True)
            if self.is_running:
                container.stop(self.name)
            container.autostart()
        self.unit.status = ActiveStatus()

    def _validate_config(self):
        """Check that charm config settings are valid.

        If the charm config is not valid, will set the unit status to BlockedStatus and
        return False.
        """
        if self.config["metric-allowlist"] and self.config["metric-denylist"]:
            raise InvalidConfigError(
                "metric-allowlist and metric-denylist are mutually exclusive"
            )

    @property
    def name(self):
        return self.app.name

    @property
    def layer(self):
        """Pebble layer for workload."""
        return Layer(
            {
                "summary": f"{self.name} layer",
                "description": f"pebble config layer for {self.name}",
                "services": {
                    self.name: {
                        "override": "replace",
                        "summary": self.name,
                        "command": (
                            "/kube-state-metrics --port=8080 --telemetry-port=8081 "
                            " ".join(
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

    @property
    def is_running(self):
        container = self.unit.get_container(self.name)
        try:
            return container.get_service(self.name).is_running()
        except ModelError:
            return False


if __name__ == "__main__":
    main(KubeStateMetricsOperator)
