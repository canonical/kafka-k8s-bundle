#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Collection of globals common to the Kafka bundle."""

BUNDLE_PATH = "releases/latest/kafka-k8s/bundle.yaml"
APP_CHARM_PATH = "tests/integration/bundle/app-charm"
ZOOKEEPER = "zookeeper-k8s"
KAFKA = "kafka-k8s"
CLIENT_CHARM_NAME = "kafka-test-app"


CONF_PATH = "/etc/kafka"
DATA_PATH = "/var/lib/kafka"
LOGS_PATH = "/var/log/kafka"
BINARIES_PATH = "/opt/kafka"
TLS_PORT = 9093
