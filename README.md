# kube-state-metrics

[![Test Suite](https://github.com/johnsca/kube-state-metrics-operator/workflows/Test%20Suite/badge.svg)](https://github.com/johnsca/kube-state-metrics-operator/actions)

[kube-state-metrics][] is a simple service that listens to the Kubernetes API
server and generates metrics about the state of the objects. This operator
charm deploys and manages [kube-state-metrics][] in a cluster, and allows for
relating to [Prometheus][] to send the metrics there for use.


## Quick Start

Assuming you already have a Kubernetes model on your Juju controller,
simply deploy this charm. If you have [Prometheus][] available either
within that model or as a cross-model offer, you can relate to it as
well:

```
juju deploy ch:kube-state-metrics
juju relate kube-state-metrics prometheus
```

## Documentation

See [the charm docs](https://charmhub.io/kube-state-metrics/docs) for
more information on using and contributing to the charm.

## Configuring the Charm

See [the charm configuration reference](https://charmhub.io/kube-state-metrics/configure)
for detailed information about how to configure the charm.


<!-- Links -->
[kube-state-metrics]: https://github.com/kubernetes/kube-state-metrics
[Prometheus]: https://charmhub.io/prometheus-k8s
