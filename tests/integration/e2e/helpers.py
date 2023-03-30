#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import random
import string
from typing import Dict

import ops
from juju.unit import Unit
from pymongo import MongoClient
from pytest_operator.plugin import OpsTest

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


def get_random_topic() -> str:
    """Return a random topic name."""
    return f"topic-{''.join(random.choices(string.ascii_lowercase, k=4))}"


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
