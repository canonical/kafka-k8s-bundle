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
)

logger = logging.getLogger(__name__)

TOPIC = get_random_topic()


def test_deploy(deploy_cluster):
    time.sleep(1)  # do nothing, await deploy_cluster


def test_cluster_is_deployed_successfully(
    juju: jubilant.Juju, kafka, zookeeper, tls, certificates
):
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
        lambda status: jubilant.all_active(status, kafka, zookeeper, DATABASE_CHARM_NAME),
        timeout=1200,
        delay=10,
    )


def test_test_app_actually_set_up(
    juju, deploy_test_app, deploy_data_integrator, kafka, integrator
):
    # producer credentials
    producer_parameters_1 = None
    producer_parameters_2 = None
    # consumer credentials
    consumer_parameters_1 = None
    consumer_parameters_2 = None

    if integrator:
        # get credentials for producers and consumers
        data_integrator_producer_1 = deploy_data_integrator(
            {"topic-name": TOPIC, "extra-user-roles": "producer"}
        )
        juju.integrate(data_integrator_producer_1, kafka)
        juju.wait(
            lambda status: jubilant.all_active(status, data_integrator_producer_1, kafka),
            timeout=1800,
            delay=10,
        )
        producer_credentials_1 = fetch_action_get_credentials(juju, data_integrator_producer_1)
        producer_parameters_1 = get_action_parameters(producer_credentials_1, TOPIC)

        data_integrator_producer_2 = deploy_data_integrator(
            {"topic-name": TOPIC, "extra-user-roles": "producer"}
        )
        juju.integrate(data_integrator_producer_2, kafka)
        juju.wait(
            lambda status: jubilant.all_active(status, data_integrator_producer_2, kafka),
            timeout=1800,
            delay=10,
        )
        producer_credentials_2 = fetch_action_get_credentials(juju, data_integrator_producer_2)
        producer_parameters_2 = get_action_parameters(producer_credentials_2, TOPIC)

        assert producer_parameters_2 != producer_parameters_1

        data_integrator_consumer_1 = deploy_data_integrator(
            {"topic-name": TOPIC, "extra-user-roles": "consumer", "consumer-group-prefix": "cg"}
        )
        juju.integrate(data_integrator_consumer_1, kafka)
        juju.wait(
            lambda status: jubilant.all_active(status, data_integrator_consumer_1, kafka),
            timeout=1800,
            delay=10,
        )
        consumer_credentials_1 = fetch_action_get_credentials(juju, data_integrator_consumer_1)
        consumer_parameters_1 = get_action_parameters(consumer_credentials_1, TOPIC)

        data_integrator_consumer_2 = deploy_data_integrator(
            {"topic-name": TOPIC, "extra-user-roles": "consumer", "consumer-group-prefix": "cg"}
        )
        juju.integrate(data_integrator_consumer_2, kafka)
        juju.wait(
            lambda status: jubilant.all_active(status, data_integrator_consumer_2, kafka),
            timeout=1800,
            delay=10,
        )
        consumer_credentials_2 = fetch_action_get_credentials(juju, data_integrator_consumer_2)
        consumer_parameters_2 = get_action_parameters(consumer_credentials_2, TOPIC)

        assert consumer_parameters_2 != consumer_parameters_1

    producer_1 = deploy_test_app(role="producer", topic_name=TOPIC, num_messages=2500)
    assert juju.status().apps[producer_1].app_status.current == "active"

    if integrator:
        # start producer
        assert producer_parameters_1
        pid = fetch_action_start_process(juju, producer_1, producer_parameters_1)
        logger.info(f"Producer process started with pid: {pid}")
    else:
        # Relate with Kafka and automatically start first producer
        juju.integrate(producer_1, kafka)
        juju.wait(
            lambda status: jubilant.all_active(status, producer_1, kafka),
            timeout=1800,
            delay=10,
        )
        logger.info(f"Producer {producer_1} related to Kafka")

    consumer_1 = deploy_test_app(role="consumer", topic_name=TOPIC, consumer_group_prefix="cg")
    assert juju.status().apps[consumer_1].app_status.current == "active"

    if integrator:
        # start consumer
        assert consumer_parameters_1
        pid = fetch_action_start_process(juju, consumer_1, consumer_parameters_1)
        logger.info(f"Consumer process started with pid: {pid}")
    else:
        # Relate with Kafka and automatically start first consumer
        juju.integrate(consumer_1, kafka)
        juju.wait(
            lambda status: jubilant.all_active(status, consumer_1, kafka),
            timeout=1800,
            delay=10,
        )
        logger.info(f"Consumer {consumer_1} related to Kafka")

    time.sleep(100)

    # deploy second consumer

    consumer_2 = deploy_test_app(role="consumer", topic_name=TOPIC, consumer_group_prefix="cg")
    assert juju.status().apps[consumer_2].app_status.current == "active"
    if integrator:
        assert consumer_parameters_2
        # start second consumer
        pid = fetch_action_start_process(juju, consumer_2, consumer_parameters_2)
        logger.info(f"Consumer process started with pid: {pid}")
    else:
        # Relate with Kafka and automatically start second consumer
        juju.integrate(consumer_2, kafka)
        juju.wait(
            lambda status: jubilant.all_active(status, consumer_2, kafka),
            timeout=1800,
            delay=10,
        )
        logger.info(f"Consumer {consumer_2} related to Kafka")

    time.sleep(100)

    # remove first consumer
    if integrator:
        pid = fetch_action_stop_process(juju, consumer_1)
        logger.info(f"Consumer 1 process stopped with pid: {pid}")
    else:
        juju.remove_relation(f"{consumer_1}:kafka-cluster", kafka)
        juju.wait(lambda status: status.apps[kafka].is_active, timeout=1200, delay=10)
        logger.info(f"Consumer {consumer_1} unrelate from Kafka")

    juju.wait(lambda status: status.apps[kafka].is_active, timeout=1800, delay=5)

    time.sleep(100)

    # deploy new producer

    producer_2 = deploy_test_app(role="producer", topic_name=TOPIC, num_messages=2000)
    assert juju.status().apps[producer_2].app_status.current == "active"
    if integrator:
        assert producer_parameters_2
        # start second producer
        pid = fetch_action_start_process(juju, producer_2, producer_parameters_2)
        logger.info(f"Producer process started with pid: {pid}")
    else:
        # Relate with Kafka and automatically start first producer
        juju.integrate(producer_2, kafka)
        juju.wait(
            lambda status: jubilant.all_active(status, producer_2, kafka),
            timeout=1800,
            delay=10,
        )
        logger.info(f"Producer {producer_2} related to Kafka")

    time.sleep(100)

    # destroy producer and consumer during teardown.

    if integrator:
        # stop process
        pid = fetch_action_stop_process(juju, producer_2)
        logger.info(f"Producer process stopped with pid: {pid}")
        pid = fetch_action_stop_process(juju, producer_1)
        logger.info(f"Producer process stopped with pid: {pid}")

        time.sleep(60)
    else:
        # stop producers
        juju.remove_relation(f"{producer_1}:kafka-cluster", kafka)
        juju.wait(lambda status: status.apps[kafka].is_active, timeout=1200, delay=10)
        logger.info(f"Producer {producer_1} unrelate from Kafka")

        juju.remove_relation(f"{producer_2}:kafka-cluster", kafka)
        juju.wait(lambda status: status.apps[kafka].is_active, timeout=1200, delay=10)
        logger.info(f"Producer {producer_2} unrelate from Kafka")

    # destroy producer and consumer during teardown.


def test_consumed_messages(juju: jubilant.Juju, deploy_data_integrator):

    # get mongodb credentials
    mongo_integrator = deploy_data_integrator({"database-name": TOPIC})

    juju.integrate(mongo_integrator, DATABASE_CHARM_NAME)
    juju.wait(
        lambda status: jubilant.all_active(status, mongo_integrator, DATABASE_CHARM_NAME),
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
