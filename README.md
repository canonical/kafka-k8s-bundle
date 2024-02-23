# Charmed Kafka K8s Bundle
[![Charmhub](https://charmhub.io/kafka-k8s-bundle/badge.svg)](https://charmhub.io/kafka-k8s-bundle)
[![Release](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/release.yaml/badge.svg)](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/release.yaml)
[![Tests](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/canonical/kafka-k8s-bundle/actions/workflows/ci.yaml)

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
###Deploy the Bundle
```bash
juju deploy kafka-k8s-bundle --channel=edge
```

