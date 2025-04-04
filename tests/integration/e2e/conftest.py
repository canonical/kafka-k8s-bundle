#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""The pytest fixtures to support cmd options for local running and CI/CD."""

import logging
import random
import string
from typing import Dict, Literal, Optional
from zipfile import ZipFile

import pytest
import yaml
from literals import (
    BUNDLE_BUILD,
    DATABASE_CHARM_NAME,
    INTEGRATOR_CHARM_NAME,
    KAFKA_CHARM_NAME,
    KAFKA_TEST_APP_CHARM_NAME,
    TLS_CHARM_NAME,
    ZOOKEEPER_CHARM_NAME,
)
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    """Defines pytest parsers."""
    parser.addoption("--tls", action="store_true", help="set tls for e2e tests")
    parser.addoption(
        "--kafka", action="store", help="name of pre-deployed kafka app", default=KAFKA_CHARM_NAME
    )
    parser.addoption(
        "--zookeeper",
        action="store",
        help="name of pre-deployed zookeeper app",
        default=ZOOKEEPER_CHARM_NAME,
    )
    parser.addoption(
        "--certificates",
        action="store",
        help="name of pre-deployed tls-certificates app",
        default=TLS_CHARM_NAME,
    )
    parser.addoption(
        "--integrator",
        action="store_true",
        help="set usage of credentials provided by the data-integrator",
    )
    parser.addoption(
        "--database",
        action="store",
        help="name of pre-deployed mongoDB instance.",
        default=DATABASE_CHARM_NAME,
    )
    parser.addoption(
        "--bundle-file",
        action="store",
        help="name of the bundle zip when provided.",
        default=BUNDLE_BUILD,
    )


def pytest_generate_tests(metafunc):
    """Processes pytest parsers."""
    tls = metafunc.config.option.tls
    if "tls" in metafunc.fixturenames:
        metafunc.parametrize("tls", [bool(tls)], scope="module")

    kafka = metafunc.config.option.kafka
    if "kafka" in metafunc.fixturenames:
        metafunc.parametrize("kafka", [kafka], scope="module")

    zookeeper = metafunc.config.option.zookeeper
    if "zookeeper" in metafunc.fixturenames:
        metafunc.parametrize("zookeeper", [zookeeper], scope="module")

    certificates = metafunc.config.option.certificates
    if "certificates" in metafunc.fixturenames:
        metafunc.parametrize("certificates", [certificates], scope="module")

    integrator = metafunc.config.option.integrator
    if "integrator" in metafunc.fixturenames:
        metafunc.parametrize("integrator", [bool(integrator)], scope="module")

    database = metafunc.config.option.database
    if "database" in metafunc.fixturenames:
        metafunc.parametrize("database", [database], scope="module")

    bundle_file = metafunc.config.option.bundle_file
    if "bundle_file" in metafunc.fixturenames:
        metafunc.parametrize("bundle_file", [bundle_file], scope="module")


### - FIXTURES - ###


@pytest.fixture(scope="module")
async def deploy_cluster(ops_test: OpsTest, bundle_file):
    """Fixture for deploying Kafka+ZK clusters."""
    if not ops_test.model:  # avoids a multitude of linting errors
        raise RuntimeError("model not set")

    logger.info(f"Deploying Bundle with file {bundle_file}")
    retcode, stdout, stderr = await ops_test.run(
        *["juju", "deploy", "--trust", "-m", ops_test.model_full_name, f"./{bundle_file}"]
    )
    assert retcode == 0, f"Deploy failed: {(stderr or stdout).strip()}"
    logger.info(stdout)

    with ZipFile(bundle_file) as fp:
        bundle = yaml.safe_load(fp.read("bundle.yaml"))

    apps = list(bundle["applications"].keys())
    logger.info(f"Applications: {','.join(apps)}")

    async with ops_test.fast_forward(fast_interval="60s"):
        await ops_test.model.wait_for_idle(
            apps=apps, idle_period=30, status="active", timeout=1800, raise_on_error=False
        )

    logger.info("Bundle deployed!")


@pytest.fixture(scope="function")
async def deploy_data_integrator(ops_test: OpsTest, kafka):
    """Factory fixture for deploying + tearing down client applications."""
    # tracks deployed app names for teardown later
    apps = []

    async def _deploy_data_integrator(config: Dict[str, str]):
        """Deploys client with specified role and uuid."""
        if not ops_test.model:  # avoids a multitude of linting errors
            raise RuntimeError("model not set")

        # uuid to avoid name clashes for same applications
        key = "".join(random.choices(string.ascii_lowercase, k=4))
        generated_app_name = f"data-integrator-{key}"
        apps.append(generated_app_name)

        logger.info(f"{generated_app_name=} - {apps=}")
        await ops_test.model.deploy(
            INTEGRATOR_CHARM_NAME,
            application_name=generated_app_name,
            num_units=1,
            series="jammy",
            channel="edge",
            config=config,
        )
        await ops_test.model.wait_for_idle(apps=[generated_app_name])

        return generated_app_name

    logger.info(f"setting up data_integrator - current apps {apps}")
    yield _deploy_data_integrator

    logger.info(f"tearing down {apps}")
    for app in apps:
        logger.info(f"tearing down {app}")
        await ops_test.model.applications[app].remove()

    await ops_test.model.wait_for_idle(apps=[kafka], idle_period=30, status="active", timeout=1800)


@pytest.fixture(scope="function")
async def deploy_test_app(ops_test: OpsTest, kafka, certificates, tls):
    """Factory fixture for deploying + tearing down client applications."""
    # tracks deployed app names for teardown later
    apps = []

    async def _deploy_test_app(
        role: Literal["producer", "consumer"],
        topic_name: str = "test-topic",
        consumer_group_prefix: Optional[str] = None,
        num_messages: int = 1500,
    ):
        """Deploys client with specified role and uuid."""
        if not ops_test.model:  # avoids a multitude of linting errors
            raise RuntimeError("model not set")

        # uuid to avoid name clashes for same applications
        key = "".join(random.choices(string.ascii_lowercase, k=4))
        generated_app_name = f"{role}-{key}"
        apps.append(generated_app_name)

        logger.info(f"{generated_app_name=} - {apps=}")

        config = {"role": role, "topic_name": topic_name, "num_messages": num_messages}

        if consumer_group_prefix:
            config["consumer_group_prefix"] = consumer_group_prefix

        await ops_test.model.deploy(
            KAFKA_TEST_APP_CHARM_NAME,
            application_name=generated_app_name,
            num_units=1,
            series="jammy",
            channel="edge",
            config=config,
        )
        await ops_test.model.wait_for_idle(
            apps=[generated_app_name], idle_period=20, status="active"
        )

        # Relate with TLS operator
        if tls:
            await ops_test.model.add_relation(generated_app_name, certificates)
            await ops_test.model.wait_for_idle(
                apps=[generated_app_name, certificates],
                idle_period=30,
                status="active",
                timeout=1800,
            )

        # Relate with MongoDB
        await ops_test.model.add_relation(generated_app_name, DATABASE_CHARM_NAME)
        await ops_test.model.wait_for_idle(
            apps=[generated_app_name, DATABASE_CHARM_NAME],
            idle_period=30,
            status="active",
            timeout=1800,
        )

        return generated_app_name

    logger.info(f"setting up test_app - current apps {apps}")
    yield _deploy_test_app

    logger.info(f"tearing down {apps}")
    # stop producers before consumers
    for app in sorted(apps, reverse=True):
        logger.info(f"tearing down {app}")
        # check if application is in the
        if app in ops_test.model.applications:
            await ops_test.model.applications[app].remove_relation(
                f"{app}:database", f"{DATABASE_CHARM_NAME}"
            )
            await ops_test.model.wait_for_idle(apps=[DATABASE_CHARM_NAME, app], idle_period=10)
            await ops_test.model.applications[app].remove()
            await ops_test.model.wait_for_idle(
                apps=[kafka], idle_period=10, status="active", timeout=1800
            )
        else:
            logger.info(f"App: {app} already removed!")

    await ops_test.model.wait_for_idle(apps=[kafka], idle_period=30, status="active", timeout=1800)
