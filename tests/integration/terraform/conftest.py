#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import typing

import jubilant
import pytest
from tests.integration.terraform.helpers import (
    CA_FILE,
    CERTIFICATES_APP_NAME,
    CORE_MODEL_NAME,
    TRAEFIK_APP_NAME,
    CosDeployer,
    TerraformDeployer,
    all_active_idle,
    get_app_list,
    get_terraform_config,
)

KRaftMode = typing.Literal["single", "multi"]
KafkaChannel = typing.Literal["4/edge", "4/beta", "4/candidate", "4/stable"]


def pytest_addoption(parser):
    """Defines pytest parsers."""
    parser.addoption(
        "--model",
        action="store",
        help="Juju model to use; if not provided, a new model "
        "will be created for each test which requires one",
    )
    parser.addoption(
        "--keep-models",
        action="store_true",
        help="Keep models handled by opstest, can be overridden in track_model",
    )
    parser.addoption(
        "--kraft-mode",
        action="store",
        help="KRaft mode to run the tests, 'single' or 'multi'",
        default="single",
    )
    parser.addoption(
        "--ingress-offer",
        action="store",
        help="The ingress offer URL to use for deployment. If not provided,"
        " Traefik K8s operator is deployed in the core model.",
        default="",
    )
    parser.addoption(
        "--kafka-channel",
        action="store",
        help="Channel to use for the Kafka charm (broker and controller)",
        default="4/edge",
    )


@pytest.fixture(scope="module")
def kraft_mode(request: pytest.FixtureRequest) -> KRaftMode:
    """Returns the KRaft mode which is used to run the tests, should be either `single` or `multi`."""
    mode = f'{request.config.getoption("--kraft-mode")}' or "single"
    if mode not in ("single", "multi"):
        raise Exception("Unknown --kraft-mode, valid options are 'single' and 'multi'")

    return mode


@pytest.fixture(scope="module")
def ingress_offer(
    request: pytest.FixtureRequest,
) -> str | None:
    offer = (
        f'{request.config.getoption("--ingress-offer")}'
        or f"admin/{CORE_MODEL_NAME}.{TRAEFIK_APP_NAME}"
    )
    return offer


@pytest.fixture(scope="module")
def kafka_channel(request: pytest.FixtureRequest) -> KafkaChannel:
    """Returns the Kafka charm channel to deploy."""
    return request.config.getoption("--kafka-channel") or "4/edge"


# -- Terraform --


@pytest.fixture()
def deploy_cluster(
    juju: jubilant.Juju,
    model_uuid: str,
    kraft_mode: KRaftMode,
    ingress_offer: str,
    kafka_channel: KafkaChannel,
):
    """Deploy the cluster in single mode."""
    terraform_deployer = TerraformDeployer(model_uuid)

    # Ensure cleanup of any previous state
    terraform_deployer.cleanup()

    config = get_terraform_config(split_mode=(kraft_mode == "multi"), kafka_channel=kafka_channel)
    config["ingress_offer"] = ingress_offer.split(":")[-1]  # Remove the controller: prefix
    tfvars_file = terraform_deployer.create_tfvars(config)

    terraform_deployer.terraform_init()
    terraform_deployer.terraform_apply(tfvars_file)


@pytest.fixture()
def enable_terraform_tls(
    model_uuid: str, kraft_mode: KRaftMode, ingress_offer: str, kafka_channel: KafkaChannel
):
    """Deploy a tls endpoint and update terraform."""
    core_juju = jubilant.Juju(model=CORE_MODEL_NAME)

    # Store the CA cert for requests
    result = core_juju.run(f"{CERTIFICATES_APP_NAME}/0", "get-ca-certificate")
    ca = result.results.get("ca-certificate")
    open(CA_FILE, "w").write(ca)

    terraform_deployer = TerraformDeployer(model_uuid)
    config = get_terraform_config(
        enable_tls=True, split_mode=(kraft_mode == "multi"), kafka_channel=kafka_channel
    )
    config["ingress_offer"] = ingress_offer.split(":")[-1]  # Remove the controller: prefix
    tfvars_file = terraform_deployer.create_tfvars(config)

    terraform_deployer.terraform_apply(tfvars_file)


@pytest.fixture()
def disable_terraform_tls(juju: jubilant.Juju, model_uuid: str, kraft_mode):
    """Remove the tls endpoint and update terraform."""
    terraform_deployer = TerraformDeployer(model_uuid)
    config = get_terraform_config(enable_tls=False, split_mode=(kraft_mode == "multi"))
    tfvars_file = terraform_deployer.create_tfvars(config)

    terraform_deployer.terraform_apply(tfvars_file)

    juju.wait(
        lambda status: all_active_idle(status, *get_app_list(kraft_mode)),
        delay=5,
        successes=6,
        timeout=1800,
    )

    juju.destroy_model(model=CORE_MODEL_NAME, force=True)


# -- Jubilant --


@pytest.fixture(scope="module")
def juju(request: pytest.FixtureRequest):
    model = request.config.getoption("--model")
    keep_models = typing.cast(bool, request.config.getoption("--keep-models"))

    if model is None:
        with jubilant.temp_model(keep=keep_models) as juju:
            juju.wait_timeout = 10 * 60
            juju.model_config({"update-status-hook-interval": "180s"})
            yield juju

            log = juju.debug_log(limit=1000)
    else:
        juju = jubilant.Juju(model=model)
        yield juju
        log = juju.debug_log(limit=1000)

    if request.session.testsfailed:
        print(log, end="")


@pytest.fixture(scope="module")
def model_uuid(juju: jubilant.Juju) -> str:
    return next(
        iter(
            mdl["model-uuid"]
            for mdl in json.loads(juju.cli("models", "--format", "json", include_model=False))[
                "models"
            ]
            if mdl["short-name"] == juju.model
        )
    )


@pytest.fixture(scope="module")
def models(juju: jubilant.Juju) -> set[str]:
    return {
        m["short-name"]
        for m in json.loads(juju.cli("models", "--format", "json", include_model=False))["models"]
    }


# -- COS --


@pytest.fixture(scope="module")
def cos_deployer():
    """Deploy COS-lite and yield the deployer. Destroys on teardown unless --keep-models."""
    # keep_models = typing.cast(bool, request.config.getoption("--keep-models"))
    deployer = CosDeployer()
    deployer.deploy()
    deployer.wait_for_active()
    yield deployer
    # if not keep_models:
    #    deployer.destroy()


@pytest.fixture()
def deploy_cluster_with_cos(
    juju: jubilant.Juju,
    model_uuid: str,
    kraft_mode: KRaftMode,
    ingress_offer: str,
    cos_deployer: CosDeployer,
):
    """Deploy the Kafka cluster with COS integration."""
    terraform_deployer = TerraformDeployer(model_uuid)
    terraform_deployer.cleanup()

    config = get_terraform_config(split_mode=(kraft_mode == "multi"))
    config["ingress_offer"] = ingress_offer.split(":")[-1]
    config["cos_offers"] = cos_deployer.get_cos_offers()
    tfvars_file = terraform_deployer.create_tfvars(config)

    terraform_deployer.terraform_init()
    terraform_deployer.terraform_apply(tfvars_file)
