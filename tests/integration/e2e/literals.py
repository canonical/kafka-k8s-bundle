#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Collection of globals common to the Kafka bundle."""

INTEGRATOR_CHARM_NAME = "data-integrator"
BUNDLE_BUILD = "build/kafka-k8s-bundle.zip"
TLS_CHARM_NAME = "self-signed-certificates"
KAFKA_CHARM_NAME = "kafka-k8s"
ZOOKEEPER_CHARM_NAME = "zookeeper-k8s"

TLS_REL_NAME = "certificates"

DATABASE_CHARM_NAME = "mongodb-k8s"
KAFKA_TEST_APP_CHARM_NAME = "kafka-test-app"
SUBSTRATE = "k8s"

KAFKA_INTERNAL_PORT = 19092
