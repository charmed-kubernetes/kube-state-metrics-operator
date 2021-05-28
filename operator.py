"""Operator framework implementation of prometheus:scrape interface.

This module currently only implements 'provides' side of prometheus:scrape.

`PrometheusScrapeTarget`_ is a class that announces an exporter target to prometheus

This interface allows you to define your exporter endpoint hostname/IP, port,
scrape_interval, scrape_timeout, and custom labels to add to exported metrics::

    class MyExporterCharm(ops.charm.CharmBase):
        def __init__(self, *args):
            super().__init__(*args)
            # -- initialize the prometheus-scrape-target interface --
            self.prom_target = PrometheusScrapeTarget(self, "prometheus-scrape-target")
            # optionally observe the relation available event to defer setting
            # up a metrics endpoint
            self.framework.observe(
                self.prom_target.on.prometheus_available, self.on_prometheus_available
            )

        def on_config_changed(self, event):
            try:
                self.prom_target.expose_scrape_target(
                    port,
                    metrics_path,
                    scrape_interval="30s",
                    scrape_timeout="15s",
                    labels={"mylabel": "myvalue"},
                )
            except PrometheusConfigError:
                logging.error("Invalid configuration")
                return


scrape_interval, scrape_timeout, and labels are all optional fields

The interface will automatically set "host=<unit_name>" if labels is not defined
by the charm developer.  Label k, v pairs must be strings.

scrape_interval and scrape_timeout are both to be strings of the form: "<int>(m|h|s)"
scrape_timeout must be shorter than scrape_interval

https://www.robustperception.io/staleness-and-promql suggests scrape_interval
should be 2 minutes or less to avoid stale data and gaps in graphs and
unavailable data during instant vector queries.
"""

import json
import logging
from datetime import timedelta
from re import search

from ops.framework import EventBase, ObjectEvents, EventSource, Object, StoredState


class PrometheusConfigError(Exception):
    """Proxy configuration isn't valid."""

    pass


class PrometheusConnected(EventBase):
    """Emitted when Prometheus is connected to this scrape-target."""

    pass


class InterfaceProvidesEvents(ObjectEvents):
    """Provide a list of triggerable events for this interface."""

    prometheus_available = EventSource(PrometheusConnected)


class PrometheusScrapeTarget(Object):
    """Define the provides side of Prometheus 'scrape' target."""

    on = InterfaceProvidesEvents()

    state = StoredState()

    def __init__(self, charm, relation_name):
        """Set up interface events and states for prometheus scrape target."""
        super().__init__(charm, relation_name)
        self._relation_name = relation_name
        self._relation = self.model.get_relation(relation_name)

        self.framework.observe(
            charm.on[relation_name].relation_joined, self._on_relation_joined
        )
        # Initialize values to be used in relation data
        self.charm = charm
        self.state.set_default(port=None)
        self.state.set_default(metrics_path=None)
        self.state.set_default(scrape_interval=None)
        self.state.set_default(scrape_timeout=None)
        self.state.set_default(labels=None)
        hostname = self.get_hostname()
        self.state.set_default(hostname=hostname)

    def get_hostname(self):
        return str(self.charm.model.get_binding(self._relation_name).network.ingress_address)

    def _on_relation_joined(self, event):
        self._update_scrape_targets()
        self.on.prometheus_available.emit()

    def _update_scrape_targets(self):
        for relation in self.model.relations[self._relation_name]:
            # no need to update data on relations with no units
            if not relation.units:
                continue
            our_unit_data = relation.data[self.model.unit]

            our_unit_data["hostname"] = self.state.hostname
            our_unit_data["port"] = str(self.state.port)
            if self.state.metrics_path:
                our_unit_data["metrics_path"] = self.state.metrics_path
            if self.state.scrape_interval:
                our_unit_data["scrape_interval"] = self.state.scrape_interval
            if self.state.scrape_timeout:
                our_unit_data["scrape_timeout"] = self.state.scrape_timeout
            if self.state.labels:
                our_unit_data["labels"] = json.dumps(dict(self.state.labels))

    def _check_interval_larger_than_timeout(self):
        if self.state.scrape_interval is None and self.state.scrape_timeout is None:
            return

        # https://github.com/prometheus/prometheus/blob/4e6a94a27d64f529932ef5f552d9d776d672ec22/config/config.go#L77  # noqa:E501
        interval_seconds = 60
        # https://github.com/prometheus/prometheus/blob/4e6a94a27d64f529932ef5f552d9d776d672ec22/config/config.go#L78  # noqa:E501
        timeout_seconds = 10

        if self.state.scrape_interval:
            interval_seconds = _calc_interval_seconds(self.state.scrape_interval)
        if self.state.scrape_timeout:
            timeout_seconds = _calc_interval_seconds(self.state.scrape_timeout)

        if timeout_seconds >= interval_seconds:
            raise PrometheusConfigError(
                "Prometheus scrape_timeout must be shorter than scrape_interval. "
                "Got interval:{} and timeout:{} seconds.".format(
                    interval_seconds, timeout_seconds
                )
            )

    def expose_scrape_target(
        self, port, metrics_path, scrape_interval=None, scrape_timeout=None, labels=None
    ):
        """Handle prometheus-scrape-target data validation and update."""
        if not port:
            raise PrometheusConfigError(
                "Must provide a port to expose this prometheus scrape target."
            )
        elif not isinstance(port, int):
            raise PrometheusConfigError(
                "Prometheus scrape target port must be a positive integer."
            )
        # must store relation data as strings
        self.state.port = port

        if labels:
            _validate_labels_format(labels)
        else:
            # Let the charmer decide on labels, but if no labels are available,
            # set host=<unit-name> as a default label for this exporter's stats
            labels = {"host": str(self.model.unit).replace("/", "-")}
            logging.debug(
                "Adding default label to scrape interface: host=%s", labels["host"]
            )
        self.state.labels = labels

        if scrape_interval:
            _validate_interval_format(scrape_interval, name="scrape_interval")
            if _calc_interval_seconds(scrape_interval) > 120:
                logging.warning(
                    "Prometheus scrape_interval may be too high. "
                    "Suggest interval of 2m or less as best practice."
                )
        self.state.scrape_interval = scrape_interval

        if scrape_timeout:
            _validate_interval_format(scrape_timeout, name="scrape_timeout")
        self.state.scrape_timeout = scrape_timeout

        self._check_interval_larger_than_timeout()

        if not isinstance(metrics_path, str):
            raise PrometheusConfigError("Prometheus metrics_path must be a string")
        self.state.metrics_path = metrics_path

        # Re-read ingress-address in case the binding has changed
        self.state.hostname = self.get_hostname()

        # after data validation, update the relations with the new scrape definition
        self._update_scrape_targets()


def _validate_labels_format(labels):
    """Raise exception if the labels provided are not in proper format."""
    if not isinstance(labels, dict):
        raise PrometheusConfigError("Labels must be a dictionary")
    else:
        for k, v in labels.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise PrometheusConfigError("Label keys and values must be strings")


def _validate_interval_format(interval, name=None):
    """Raise exception if the interval provided is not in proper format."""
    valid_config = search(r"^(\d+)(h|m|s)$", interval)
    duration = valid_config.group(1) or None
    magnitude = valid_config.group(2) or None
    if not duration or not magnitude:
        raise PrometheusConfigError(
            "Prometheus {} must be expressed as an integer followed "
            "by s or m or h. e.g. 15s or 2m or 1h. ".format(name)
        )


def _calc_interval_seconds(interval):
    r = search(r"^(\d+)(h|m|s)$", interval)
    duration = int(r.group(1))
    magnitude = r.group(2)
    if magnitude == "m":
        return int(timedelta(minutes=duration).total_seconds())
    elif magnitude == "h":
        return int(timedelta(hours=duration).total_seconds())
    elif magnitude == "s":
        return int(duration)
