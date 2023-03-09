# Charmed Kafka K8s Bundle

[![Bundle update available](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/on_bundle_update_available.yaml/badge.svg)](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/on_bundle_update_available.yaml)
[![Integration tests](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/ci.yaml/badge.svg)](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/ci.yaml)
[![Release to latest/edge](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/release.yaml/badge.svg)](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/release.yaml)
[![Charmhub](https://charmhub.io/kafka-k8s-bundle/badge.svg)](https://charmhub.io/kafka-k8s-bundle)

[Charmed Kafka K8s bundle](https://charmhub.io/kafka-k8s-bundle) deploys Kafka + Zookeeper with TLS support. This includes encryption between nodes in the cluster as well as client communication. Manual, Day 2 operations for deploying and operating Apache Kafka, topic creation, client authentication, ACL management and more are all handled automatically using the [Juju Operator Lifecycle Manager](https://juju.is/docs/olm).

## Key Features
- SASL/SCRAM auth for Broker-Broker and Client-Broker authenticaion enabled by default.
- Access control management supported with user-provided ACL lists.
- Fault-tolerance, replication and high-availability out-of-the-box.
- Streamlined topic-creation through [Juju Actions](https://juju.is/docs/olm/working-with-actions) and [application relations](https://juju.is/docs/olm/relations)

## Usage
The steps outlined below are based on the assumption that you are deploying the charm locally with the latest LTS of Ubuntu.  If you are using another version of Ubuntu or another operating system, the process may be different.

### Install and Configure Dependencies
```bash
sudo snap install microk8s --classic
sudo snap install juju --classic
microk8s enable dns hostpath-storage
```

### Create a [Juju controller](https://juju.is/docs/olm/create-a-controller)
```bash
juju bootstrap microk8s
```

### Create a Model in Juju
```bash
juju add-model kafka
juju switch kafka
```

### Deploy the Bundle
```bash
juju deploy kafka-k8s-bundle --channel=edge
```