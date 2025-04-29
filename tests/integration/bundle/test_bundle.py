#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import time
from zipfile import ZipFile

import jubilant
import pytest
import yaml
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


def test_verify_tls_flags_consistency(bundle_file, tls):
    """Verify consistency of TLS settings in the bundle file with flags set on the test."""
    with ZipFile(bundle_file) as fp:
        bundle_data = yaml.safe_load(fp.read("bundle.yaml"))

    applications = []

    bundle_tls = False
    for app in bundle_data["applications"]:
        applications.append(app)
        if TLS_CHARM_NAME in app:
            bundle_tls = True

    assert tls == bundle_tls


def test_deploy_bundle_active(juju: jubilant.Juju, bundle_file, tls):
    """Deploy the bundle."""
    logger.info(f"Deploying Bundle with file {bundle_file}")
    stdout = juju.cli(
        *["deploy", "--trust", "-m", juju.model, f"./{bundle_file}"], include_model=False
    )
    juju.trust(KAFKA, scope="cluster")
    logger.info(stdout)

    juju.wait(lambda status: jubilant.all_active(status), timeout=1800)


def test_active_zookeeper(juju: jubilant.Juju):
    """Test the status the correct status of Zookeeper."""
    zookeeper_hosts = [unit.address for unit in juju.status().apps[ZOOKEEPER].units.values()]
    assert ping_servers(zookeeper_hosts)


def test_deploy_app_charm_relate(juju: jubilant.Juju, bundle_file, tls):
    """Deploy dummy app and relate with Kafka and TLS operator."""
    with ZipFile(bundle_file) as fp:
        bundle_data = yaml.safe_load(fp.read("bundle.yaml"))

    applications = list(bundle_data["applications"].keys())

    config = {"role": "producer", "topic_name": TOPIC, "num_messages": 50}
    juju.deploy(
        CLIENT_CHARM_NAME,
        app=PRODUCER,
        num_units=1,
        channel="edge",
        config=config,
    )
    juju.wait(lambda status: jubilant.all_active(status, apps=[PRODUCER]), timeout=600)

    if tls:
        juju.integrate(PRODUCER, TLS_CHARM_NAME)

    juju.wait(
        lambda status: jubilant.all_active(status, apps=applications), timeout=1200, delay=10
    )
    juju.integrate(KAFKA, PRODUCER)

    juju.wait(
        lambda status: jubilant.all_active(status, apps=applications + [PRODUCER]),
        timeout=1000,
        delay=10,
    )

    status = juju.status()
    for app in applications + [PRODUCER]:
        assert status.apps[app].app_status.current == "active"

    time.sleep(100)

    check_produced_messages(juju.model, f"{PRODUCER}/0")


def test_apps_up_and_running(juju: jubilant.Juju, usernames):
    """Test that all apps are up and running."""
    status = juju.status()
    zookeeper_hosts = [unit.address for unit in status.apps[ZOOKEEPER].units.values()]
    assert ping_servers(zookeeper_hosts)

    for unit in status.apps[ZOOKEEPER].units:
        assert "sslQuorum=true" in check_properties(model_full_name=juju.model, unit=unit)

    # implicitly tests setting of kafka app data
    zookeeper_usernames, zookeeper_uri = get_zookeeper_connection(
        unit_name=f"{KAFKA}/0", owner=ZOOKEEPER, model_full_name=juju.model
    )
    assert zookeeper_uri
    assert len(zookeeper_usernames) > 0

    usernames.update(get_kafka_users(f"{KAFKA}/0", juju.model))

    ip_address = get_address(juju.status(), app_name=KAFKA, unit_num="0")
    bootstrap_server = f"{ip_address}:{TLS_PORT}"

    for username in usernames:
        check_user(
            username=username,
            bootstrap_server=bootstrap_server,
            model_full_name=juju.model,
            unit_name=f"{KAFKA}/0",
        )

    for acl in load_acls(
        model_full_name=juju.model,
        bootstrap_server=bootstrap_server,
        unit_name=f"{KAFKA}/0",
    ):
        assert acl.username in usernames
        assert acl.operation in ["CREATE", "READ", "WRITE", "DESCRIBE"]
        assert acl.resource_type in ["GROUP", "TOPIC"]
        if acl.resource_type == "TOPIC":
            assert acl.resource_name == TOPIC

    zookeeper_hosts = [unit.address for unit in juju.status().apps[ZOOKEEPER].units.values()]
    assert ping_servers(zookeeper_hosts)
