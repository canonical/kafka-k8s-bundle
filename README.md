# Kafka K8s Bundle

[![Bundle update available](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/on_bundle_update_available.yaml/badge.svg)](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/on_bundle_update_available.yaml)
[![Integration tests](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/ci.yaml/badge.svg)](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/ci.yaml)
[![Release to latest/edge](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/release.yaml/badge.svg)](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/release.yaml)
[![Charmhub](https://charmhub.io/kafka-k8s-bundle/badge.svg)](https://charmhub.io/kafka-k8s-bundle)

This repository contains the k8s charm bundles for Kafka.

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

