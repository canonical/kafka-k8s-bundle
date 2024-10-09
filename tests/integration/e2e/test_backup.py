#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import json
import logging
import socket

import boto3
import pytest
import pytest_microceph
from mypy_boto3_s3.service_resource import Bucket
from pytest_operator.plugin import OpsTest
from tests.integration.e2e.helpers import (
    create_topic,
    get_random_topic,
    read_topic_config,
    write_topic_message_size_config,
)

logger = logging.getLogger(__name__)

TOPIC = get_random_topic()
S3_INTEGRATOR = "s3-integrator"
S3_CHANNEL = "latest/stable"


@pytest.fixture(scope="session")
def cloud_credentials(microceph: pytest_microceph.ConnectionInformation) -> dict[str, str]:
    """Read cloud credentials."""
    return {
        "access-key": microceph.access_key_id,
        "secret-key": microceph.secret_access_key,
    }


@pytest.fixture(scope="session")
def cloud_configs(microceph: pytest_microceph.ConnectionInformation):
    host_ip = socket.gethostbyname(socket.gethostname())
    return {
        "endpoint": f"http://{host_ip}",
        "bucket": microceph.bucket,
        "path": "mysql",
        "region": "",
    }


@pytest.fixture(scope="function")
def s3_bucket(cloud_credentials, cloud_configs):

    session = boto3.Session(
        aws_access_key_id=cloud_credentials["access-key"],
        aws_secret_access_key=cloud_credentials["secret-key"],
        region_name=cloud_configs["region"] if cloud_configs["region"] else None,
    )
    s3 = session.resource("s3", endpoint_url=cloud_configs["endpoint"])
    bucket = s3.Bucket(cloud_configs["bucket"])
    yield bucket


@pytest.mark.skip_if_deployed
@pytest.mark.abort_on_fail
async def test_deploy(ops_test: OpsTest, deploy_cluster):
    await asyncio.sleep(0)  # do nothing, await deploy_cluster


@pytest.mark.abort_on_fail
async def test_set_up_deployment(
    ops_test: OpsTest,
    kafka,
    zookeeper,
    cloud_configs,
    cloud_credentials,
    s3_bucket,
):
    assert ops_test.model.applications[kafka].status == "active"
    assert ops_test.model.applications[zookeeper].status == "active"
    await ops_test.model.deploy(S3_INTEGRATOR, channel=S3_CHANNEL)
    await ops_test.model.wait_for_idle(apps=[S3_INTEGRATOR], status="blocked", timeout=1000)

    logger.info("Syncing credentials")

    await ops_test.model.applications[S3_INTEGRATOR].set_config(cloud_configs)
    leader_unit = ops_test.model.applications[S3_INTEGRATOR].units[0]

    sync_action = await leader_unit.run_action(
        "sync-s3-credentials",
        **cloud_credentials,
    )
    await sync_action.wait()
    await ops_test.model.add_relation(zookeeper, S3_INTEGRATOR)
    await ops_test.model.wait_for_idle(
        apps=[zookeeper, S3_INTEGRATOR],
        status="active",
        timeout=1000,
    )

    # bucket exists
    assert s3_bucket.meta.client.head_bucket(Bucket=s3_bucket.name)


@pytest.mark.abort_on_fail
async def test_create_restore_backup(ops_test: OpsTest, s3_bucket: Bucket, kafka, zookeeper):

    initial_size = 123_123
    updated_size = 456_456

    logger.info("Creating topic")

    create_topic(model_full_name=ops_test.model_full_name, app_name=kafka, topic=TOPIC)
    write_topic_message_size_config(
        model_full_name=ops_test.model_full_name, app_name=kafka, topic=TOPIC, size=initial_size
    )
    assert f"max.message.bytes={initial_size}" in read_topic_config(
        model_full_name=ops_test.model_full_name, app_name=kafka, topic=TOPIC
    )

    logger.info("Creating initial backup")

    for unit in ops_test.model.applications[zookeeper].units:
        if await unit.is_leader_from_status():
            leader_unit = unit

    create_action = await leader_unit.run_action("create-backup")
    await create_action.wait()

    list_action = await leader_unit.run_action("list-backups")
    response = await list_action.wait()

    backups = json.loads(response.results.get("backups", "[]"))
    assert len(backups) == 1

    logger.info("Restoring backup")

    write_topic_message_size_config(
        model_full_name=ops_test.model_full_name, app_name=kafka, topic=TOPIC, size=updated_size
    )

    assert f"max.message.bytes={updated_size}" in read_topic_config(
        model_full_name=ops_test.model_full_name, app_name=kafka, topic=TOPIC
    )

    backup_to_restore = backups[0]["id"]
    list_action = await leader_unit.run_action("restore", **{"backup-id": backup_to_restore})
    await ops_test.model.wait_for_idle(
        apps=[zookeeper, kafka], status="active", timeout=1000, idle_period=30
    )
    assert f"max.message.bytes={initial_size}" in read_topic_config(
        model_full_name=ops_test.model_full_name, app_name=kafka, topic=TOPIC
    )

    assert ops_test.model.applications[kafka].status == "active"
    assert ops_test.model.applications[zookeeper].status == "active"