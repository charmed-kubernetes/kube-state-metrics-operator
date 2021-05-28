# kube-state-metrics

kube-state-metrics is a simple service that listens to the Kubernetes API
server and generates metrics about the state of the objects. This Operator
charm deploys and manages kube-state-metrics in a cluster, and allows for
relating to Prometheus to send the metrics there for use.


## Usage

Assuming you already have a Kubernetes model on your Juju controller,
simply deploy this charm. If you have a Prometheus available either
within that model or as a cross-model offer, you can relate to it as
well:

```
juju deploy ch:kube-state-metrics
juju relate kube-state-metrics prometheus
```
