#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging
from pathlib import Path

import pytest
import yaml
from pytest_operator.plugin import OpsTest
from tests.integration.bundle.helpers import (
    check_produced_messages,
    check_properties,
    check_user,
    get_address,
    get_kafka_users,
    get_zookeeper_connection,
    load_acls,
    ping_servers,
)
from tests.integration.bundle.literals import (
    BUNDLE_PATH,
    CLIENT_CHARM_NAME,
    KAFKA,
    TLS_CHARM_NAME,
    TLS_PORT,
    ZOOKEEPER,
)

logger = logging.getLogger(__name__)

PRODUCER = "producer"
CONSUMER = "consumer"
TOPIC = "test-topic"


@pytest.fixture(scope="module")
def usernames():
    return set()


@pytest.mark.abort_on_fail
async def test_deploy_bundle_active(ops_test: OpsTest):
    """Deploy the bundle."""
    bundle_data = yaml.safe_load(Path(BUNDLE_PATH).read_text())
    applications = []

    for app in bundle_data["applications"]:
        applications.append(app)

    retcode, stdout, stderr = await ops_test.run(
        *["juju", "deploy", "--trust", "-m", ops_test.model_full_name, f"./{BUNDLE_PATH}"]
    )
    assert retcode == 0, f"Deploy failed: {(stderr or stdout).strip()}"
    logger.info(stdout)
    await ops_test.model.wait_for_idle(timeout=2000, idle_period=30, status="active")
    for app in applications:
        assert ops_test.model.applications[app].status == "active"


@pytest.mark.abort_on_fail
async def test_active_zookeeper(ops_test: OpsTest):
    """Test the status the correct status of Zookeeper."""
    assert await ping_servers(ops_test, ZOOKEEPER)


@pytest.mark.abort_on_fail
async def test_deploy_app_charm_relate(ops_test: OpsTest):
    """Deploy dummy app and relate with Kafka and TLS operator."""
    bundle_data = yaml.safe_load(Path(BUNDLE_PATH).read_text())
    applications = []

    tls = False
    for app in bundle_data["applications"]:
        applications.append(app)
        if TLS_CHARM_NAME in app:
            tls = True

    config = {"role": "producer", "topic_name": TOPIC, "num_messages": 50}
    await ops_test.model.deploy(
        CLIENT_CHARM_NAME,
        application_name=PRODUCER,
        num_units=1,
        series="jammy",
        channel="edge",
        config=config,
    )
    await ops_test.model.wait_for_idle(apps=[PRODUCER])

    if tls:
        await ops_test.model.add_relation(PRODUCER, TLS_CHARM_NAME)

    await ops_test.model.wait_for_idle(
        apps=applications, timeout=1200, idle_period=30, status="active"
    )
    await ops_test.model.add_relation(KAFKA, PRODUCER)

    await ops_test.model.wait_for_idle(
        apps=applications + [PRODUCER], status="active", timeout=1000, idle_period=30
    )

    for app in applications + [PRODUCER]:
        assert ops_test.model.applications[app].status == "active"

    await asyncio.sleep(10)

    check_produced_messages(ops_test.model_full_name, f"{PRODUCER}/0")


@pytest.mark.abort_on_fail
async def test_apps_up_and_running(ops_test: OpsTest, usernames):
    """Test that all apps are up and running."""
    assert await ping_servers(ops_test, ZOOKEEPER)

    for unit in ops_test.model.applications[ZOOKEEPER].units:
        assert "sslQuorum=true" in check_properties(
            model_full_name=ops_test.model_full_name, unit=unit.name
        )

    # implicitly tests setting of kafka app data
    zookeeper_usernames, zookeeper_uri = get_zookeeper_connection(
        unit_name=f"{KAFKA}/0", owner=ZOOKEEPER, model_full_name=ops_test.model_full_name
    )
    assert zookeeper_uri
    assert len(zookeeper_usernames) > 0

    usernames.update(get_kafka_users(f"{KAFKA}/0", ops_test.model_full_name))

    ip_address = await get_address(ops_test, app_name=KAFKA, unit_num="0")
    bootstrap_server = f"{ip_address}:{TLS_PORT}"

    for username in usernames:
        check_user(
            username=username,
            bootstrap_server=bootstrap_server,
            model_full_name=ops_test.model_full_name,
            unit_name=f"{KAFKA}/0",
        )

    for acl in load_acls(
        model_full_name=ops_test.model_full_name,
        bootstrap_server=bootstrap_server,
        unit_name=f"{KAFKA}/0",
    ):
        assert acl.username in usernames
        assert acl.operation in ["CREATE", "READ", "WRITE", "DESCRIBE"]
        assert acl.resource_type in ["GROUP", "TOPIC"]
        if acl.resource_type == "TOPIC":
            assert acl.resource_name == TOPIC
    assert await ping_servers(ops_test, ZOOKEEPER)
