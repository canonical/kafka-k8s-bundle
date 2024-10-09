#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import random
import string
from subprocess import PIPE, STDOUT, CalledProcessError, check_output
from typing import Dict

import ops
from juju.unit import Unit
from pymongo import MongoClient
from pytest_operator.plugin import OpsTest
from tests.integration.e2e.literals import SUBSTRATE

logger = logging.getLogger()


def check_produced_and_consumed_messages(uris: str, collection_name: str):
    """Check that messages produced and consumed are consistent."""
    logger.debug(f"MongoDB uris: {uris}")
    logger.debug(f"Topic: {collection_name}")
    produced_messages = []
    consumed_messages = []
    logger.info(f"URI: {uris}")
    try:
        client = MongoClient(
            uris,
            directConnection=True,
            connect=False,
            serverSelectionTimeoutMS=1000,
            connectTimeoutMS=2000,
        )
        db = client[collection_name]
        consumer_collection = db["consumer"]
        producer_collection = db["producer"]

        logger.info(f"Number of messages from consumer: {consumer_collection.count_documents({})}")
        logger.info(f"Number of messages from producer: {producer_collection.count_documents({})}")
        assert consumer_collection.count_documents({}) > 0
        assert producer_collection.count_documents({}) > 0
        cursor = consumer_collection.find({})
        for document in cursor:
            consumed_messages.append((document["origin"], document["content"]))

        cursor = producer_collection.find({})
        for document in cursor:
            produced_messages.append((document["origin"], document["content"]))

        logger.info(f"Number of produced messages: {len(produced_messages)}")
        logger.info(f"Number of unique produced messages: {len(set(produced_messages))}")
        logger.info(f"Number of consumed messages: {len(consumed_messages)}")
        logger.info(f"Number of unique consumed messages: {len(set(consumed_messages))}")

        assert len(consumed_messages) >= len(produced_messages)
        assert abs(len(consumed_messages) - len(produced_messages)) < 3
        if len(consumed_messages) < len(produced_messages):
            missing_elem = list(set(produced_messages) - set(consumed_messages))
            logger.error(missing_elem)

        client.close()
    except Exception as e:
        logger.error("Cannot connect to MongoDB collection.")
        raise e


async def fetch_action_get_credentials(unit: Unit) -> Dict:
    """Helper to run an action to fetch connection info.

    Args:
        unit: The juju unit on which to run the get_credentials action for credentials
    Returns:
        A dictionary with the username, password and access info for the service.
    """
    action = await unit.run_action(action_name="get-credentials")
    result = await action.wait()
    return result.results


async def kubectl_delete(ops_test: OpsTest, unit: ops.model.Unit, wait: bool = True) -> None:
    """Delete the underlying pod for a unit."""
    kubectl_cmd = (
        "microk8s",
        "kubectl",
        "delete",
        "pod",
        f"--wait={wait}",
        f"-n{ops_test.model_name}",
        unit.name.replace("/", "-"),
    )
    logger.info(f"Command: {kubectl_cmd}")
    ret_code, _, _ = await ops_test.run(*kubectl_cmd)
    assert ret_code == 0, "Unit failed to delete"


async def scale_application(
    ops_test: OpsTest, application_name: str, desired_count: int, wait: bool = True
) -> None:
    """Scale a given application to the desired unit count.

    Args:
        ops_test: The ops test framework
        application_name: The name of the application
        desired_count: The number of units to scale to
        wait: Boolean indicating whether to wait until units
            reach desired count.
    """
    if len(ops_test.model.applications[application_name].units) == desired_count:
        return
    await ops_test.model.applications[application_name].scale(desired_count)

    if desired_count > 0 and wait:
        async with ops_test.fast_forward():
            await ops_test.model.wait_for_idle(
                apps=[application_name],
                status="active",
                timeout=15 * 60,
                wait_for_exact_units=desired_count,
                raise_on_blocked=True,
            )

    assert len(ops_test.model.applications[application_name].units) == desired_count


async def get_address(ops_test: OpsTest, app_name, unit_num=0) -> str:
    """Get the address for a unit."""
    status = await ops_test.model.get_status()  # noqa: F821
    address = status["applications"][app_name]["units"][f"{app_name}/{unit_num}"]["address"]
    return address


def get_action_parameters(credentials: dict, topic_name: str):
    """Construct parameter dictionary needed to stark consumer/producer with the action."""
    logger.info(f"Credentials: {credentials}")
    assert "kafka" in credentials
    action_data = {
        "servers": credentials["kafka"]["endpoints"],
        "username": credentials["kafka"]["username"],
        "password": credentials["kafka"]["password"],
        "topic-name": topic_name,
    }
    if "consumer-group-prefix" in credentials["kafka"]:
        action_data["consumer-group-prefix"] = credentials["kafka"]["consumer-group-prefix"]
    return action_data


async def fetch_action_start_process(unit: Unit, action_params: Dict[str, str]) -> Dict:
    """Helper to run an action to start consumer/producer.

    Args:
        unit: the target unit.
        action_params: A dictionary that contains all commands parameters.

    Returns:
        A dictionary with the result of the action.
    """
    action = await unit.run_action(action_name="start-process", **action_params)
    result = await action.wait()
    return result.results


async def fetch_action_stop_process(unit: Unit) -> Dict:
    """Helper to run an action to stop consumer/producer.

    Args:
        unit: the target unit.

    Returns:
        A dictionary with the result of the action.
    """
    action = await unit.run_action(action_name="stop-process")
    result = await action.wait()
    return result.results


def get_random_topic() -> str:
    """Return a random topic name."""
    return f"topic-{''.join(random.choices(string.ascii_lowercase, k=4))}"


def create_topic(model_full_name: str, app_name: str, topic: str) -> None:
    """Helper to create a topic.

    Args:
        model_full_name: Juju model
        app_name: Kafka app name in the Juju model
        topic: the desired topic to configure
    """
    container = "--container kafka" if SUBSTRATE == "k8s" else ""
    try:
        check_output(
            f"JUJU_MODEL={model_full_name} juju ssh {container} {app_name}/0 sudo -i 'charmed-kafka.topics --create --topic {topic} --bootstrap-server localhost:19092 "
            f"--command-config /var/snap/charmed-kafka/current/etc/kafka/client.properties'",
            stderr=STDOUT,
            shell=True,
            universal_newlines=True,
        )

    except CalledProcessError as e:
        logger.error(f"command '{e.cmd}' return with error (code {e.returncode}): {e.output}")
        raise


def write_topic_message_size_config(
    model_full_name: str, app_name: str, topic: str, size: int
) -> None:
    """Helper to configure a topic's message max size.

    Args:
        model_full_name: Juju model
        app_name: Kafka app name in the Juju model
        topic: the desired topic to configure
        size: the maximal message size in bytes
    """
    container = "--container kafka" if SUBSTRATE == "k8s" else ""
    try:
        result = check_output(
            f"JUJU_MODEL={model_full_name} juju ssh {container} {app_name}/0 sudo -i 'charmed-kafka.configs --bootstrap-server localhost:19092 "
            f"--entity-type topics --entity-name {topic} --alter --add-config max.message.bytes={size} --command-config /var/snap/charmed-kafka/current/etc/kafka/client.properties'",
            stderr=STDOUT,
            shell=True,
            universal_newlines=True,
        )

    except CalledProcessError as e:
        logger.error(f"command '{e.cmd}' return with error (code {e.returncode}): {e.output}")
        raise
    assert f"Completed updating config for topic {topic}." in result


def read_topic_config(model_full_name: str, app_name: str, topic: str) -> str:
    """Helper to get a topic's configuration.

    Args:
        model_full_name: Juju model
        app_name: Kafka app name in the Juju model
        topic: the desired topic to read the configuration from
    """
    container = "--container kafka" if SUBSTRATE == "k8s" else ""
    try:
        result = check_output(
            f"JUJU_MODEL={model_full_name} juju ssh {container} {app_name}/0 sudo -i 'charmed-kafka.configs --bootstrap-server localhost:19092 "
            f"--entity-type topics --entity-name {topic} --describe --command-config /var/snap/charmed-kafka/current/etc/kafka/client.properties'",
            stderr=PIPE,
            shell=True,
            universal_newlines=True,
        )

    except CalledProcessError as e:
        logger.error(f"command '{e.cmd}' return with error (code {e.returncode}): {e.output}")
        raise
    return result
