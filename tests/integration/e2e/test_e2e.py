#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import time

import jubilant
from tests.integration.e2e.helpers import jubilant_all_units_idle
from tests.integration.e2e.literals import KAFKA_CHARM_NAME

logger = logging.getLogger(__name__)


def test_deploy(deploy_cluster):
    time.sleep(0)  # do nothing, await deploy_cluster


def test_cluster_is_deployed_successfully(
    juju: jubilant.Juju, kafka, zookeeper, tls, certificates
):
    status = juju.status()
    assert status.apps[kafka].app_status.current == "active"
    assert status.apps[zookeeper].app_status.current == "active"

    if tls:
        assert status.apps[certificates].app_status.current == "active"


def test_clients_actually_set_up(juju: jubilant.Juju, deploy_data_integrator, kafka):
    producer = deploy_data_integrator({"extra-user-roles": "producer", "topic-name": "test-topic"})
    consumer = deploy_data_integrator({"extra-user-roles": "producer", "topic-name": "test-topic"})

    juju.integrate(producer, KAFKA_CHARM_NAME)
    juju.wait(
        lambda status: jubilant.all_active(status, apps=[producer, KAFKA_CHARM_NAME]),
        timeout=1800,
        delay=10,
    )

    juju.integrate(consumer, KAFKA_CHARM_NAME)
    juju.wait(
        lambda status: jubilant.all_active(status, apps=[consumer, KAFKA_CHARM_NAME]),
        timeout=1800,
        delay=10,
    )

    status = juju.status()
    assert status.apps[consumer].app_status.current == "active"
    assert status.apps[producer].app_status.current == "active"

    juju.remove_relation(f"{consumer}:kafka", f"{kafka}")
    juju.wait(lambda status: jubilant_all_units_idle(status, apps=[consumer, kafka]), delay=5)

    juju.remove_relation(f"{producer}:kafka", f"{kafka}")
    juju.wait(lambda status: jubilant_all_units_idle(status, apps=[producer, kafka]), delay=5)


def test_clients_actually_tear_down_after_test_exit(juju):
    status = juju.status()
    assert "consumer" not in status.apps.keys()
    assert "producer" not in status.apps.keys()
