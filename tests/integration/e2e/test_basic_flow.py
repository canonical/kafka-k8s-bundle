#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import time

import jubilant
from literals import DATABASE_CHARM_NAME
from tests.integration.e2e.helpers import (
    check_produced_and_consumed_messages,
    fetch_action_get_credentials,
    fetch_action_start_process,
    fetch_action_stop_process,
    get_action_parameters,
    get_address,
    get_random_topic,
    jubilant_all_units_idle,
    scale_application,
)

logger = logging.getLogger(__name__)

TOPIC = get_random_topic()


def test_deploy(deploy_cluster):
    time.sleep(1)  # do nothing, wait for deploy_cluster


def test_cluster_is_deployed_successfully(juju, kafka, zookeeper, tls, certificates):
    status = juju.status()
    assert status.apps[kafka].app_status.current == "active"
    assert status.apps[zookeeper].app_status.current == "active"

    if tls:
        assert status.apps[certificates].app_status.current == "active"

    # deploy MongoDB

    juju.deploy(
        DATABASE_CHARM_NAME,
        app=DATABASE_CHARM_NAME,
        num_units=1,
        channel="5/edge",
    )
    juju.wait(
        lambda status: jubilant.all_active(status, apps=[kafka, zookeeper, DATABASE_CHARM_NAME]),
        timeout=1200,
        delay=10,
    )


def test_test_app_actually_set_up(
    juju, deploy_test_app, kafka, deploy_data_integrator, integrator
):
    # consumer and producer params when deploying with data-integrator
    producer_parameters = None
    consumer_parameters = None
    if integrator:
        # deploy integrators and get credentials
        data_integrator_producer = deploy_data_integrator(
            {"topic-name": TOPIC, "extra-user-roles": "producer"}
        )

        juju.integrate(data_integrator_producer, kafka)
        juju.wait(
            lambda status: jubilant.all_active(status, apps=[data_integrator_producer, kafka]),
            timeout=1800,
            delay=10,
        )
        producer_credentials = fetch_action_get_credentials(juju, data_integrator_producer)
        producer_parameters = get_action_parameters(producer_credentials, TOPIC)

        data_integrator_consumer = deploy_data_integrator(
            {"topic-name": TOPIC, "extra-user-roles": "consumer"}
        )
        juju.integrate(data_integrator_consumer, kafka)
        juju.wait(
            lambda status: jubilant.all_active(status, apps=[data_integrator_consumer, kafka]),
            timeout=1800,
            delay=10,
        )
        consumer_credentials = fetch_action_get_credentials(juju, data_integrator_consumer)
        consumer_parameters = get_action_parameters(consumer_credentials, TOPIC)

        assert producer_parameters != consumer_parameters

    # deploy producer and consumer
    producer = deploy_test_app(role="producer", topic_name=TOPIC)
    assert juju.status().apps[producer].app_status.current == "active"

    if integrator:
        # start producer with action
        assert producer_parameters
        pid = fetch_action_start_process(juju, producer, producer_parameters)
        logger.info(f"Producer process started with pid: {pid}")
    else:
        # Relate with Kafka and automatically start producer
        juju.integrate(producer, kafka)
        juju.wait(
            lambda status: jubilant.all_active(status, apps=[producer, kafka]),
            timeout=1800,
            delay=10,
        )
        logger.info(f"Producer {producer} related to Kafka")

    consumer = deploy_test_app(role="consumer", topic_name=TOPIC)
    assert juju.status().apps[consumer].app_status.current == "active"

    if integrator:
        # start consumer with action
        assert consumer_parameters
        pid = fetch_action_start_process(juju, consumer, consumer_parameters)
        logger.info(f"Consumer process started with pid: {pid}")
    else:
        # Relate with Kafka and automatically start consumer
        juju.integrate(consumer, kafka)
        juju.wait(
            lambda status: jubilant.all_active(status, apps=[consumer, kafka]),
            timeout=1800,
            delay=10,
        )
        logger.info(f"Consumer {consumer} related to Kafka")

    time.sleep(100)

    # scale up producer
    logger.info("Scale up producer")
    juju.add_unit(producer, num_units=2)
    juju.wait(
        lambda status: len(status.apps[producer].units) == 3 and status.apps[producer].is_active,
        timeout=1200,
        delay=15,
    )

    if integrator:
        # start producer process on new units
        assert producer_parameters
        pid_1 = fetch_action_start_process(juju, producer, producer_parameters, unit_num=1)
        logger.info(f"Producer process started with pid: {pid_1}")
        pid_2 = fetch_action_start_process(juju, producer, producer_parameters, unit_num=2)
        logger.info(f"Producer process started with pid: {pid_2}")

    time.sleep(100)

    logger.info("Scale up consumer")
    juju.add_unit(consumer, num_units=2)
    juju.wait(
        lambda status: len(status.apps[consumer].units) == 3 and status.apps[consumer].is_active,
        timeout=1200,
        delay=15,
    )

    if integrator:
        # start consumer process on new units
        assert consumer_parameters
        pid_1 = fetch_action_start_process(juju, consumer, consumer_parameters, unit_num=1)
        logger.info(f"Consumer process started with pid: {pid_1}")
        pid_1 = fetch_action_start_process(juju, consumer, consumer_parameters, unit_num=2)
        logger.info(f"Consumer process started with pid: {pid_2}")

    time.sleep(100)

    # skip scale down for the moment due the scale down bug in juju: https://bugs.launchpad.net/juju/+bug/1977582

    logger.info("Scale down")
    scale_application(juju, application_name=producer, desired_count=1)
    scale_application(juju, application_name=consumer, desired_count=1)

    juju.wait(
        lambda status: jubilant_all_units_idle(status, apps=[producer, consumer])
        and jubilant.all_active(status, apps=[producer, consumer]),
        timeout=1000,
        delay=5,
    )

    logger.info("End scale down")

    # Stop producers first
    if integrator:
        fetch_action_stop_process(juju, producer)
    else:
        juju.remove_relation(f"{producer}:kafka-cluster", f"{kafka}")

    time.sleep(60)

    # Then stop consumers
    if integrator:
        fetch_action_stop_process(juju, consumer)
    else:
        juju.remove_relation(f"{consumer}:kafka-cluster", f"{kafka}")

    time.sleep(30)

    # destroy producer and consumer during teardown.
    logger.info("End of the test!")


def test_consumed_messages(juju: jubilant.Juju, deploy_data_integrator):

    # get mongodb credentials
    mongo_integrator = deploy_data_integrator({"database-name": TOPIC})

    juju.integrate(mongo_integrator, DATABASE_CHARM_NAME)
    juju.wait(
        lambda status: jubilant.all_active(status, apps=[mongo_integrator, DATABASE_CHARM_NAME]),
        timeout=1800,
        delay=10,
    )

    credentials = fetch_action_get_credentials(juju, mongo_integrator)

    logger.info(f"Credentials: {credentials}")

    uris = credentials["mongodb"]["uris"]

    address = get_address(juju, app_name=DATABASE_CHARM_NAME)

    hostname = "mongodb-k8s-0.mongodb-k8s-endpoints"

    uri = str(uris).replace(hostname, address)

    check_produced_and_consumed_messages(uri, TOPIC)

    juju.remove_application(DATABASE_CHARM_NAME)
