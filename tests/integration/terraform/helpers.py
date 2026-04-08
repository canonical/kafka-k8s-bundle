#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Terraform deployment helpers for integration tests."""

import json
import logging
import shutil
import socket
import subprocess
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, Optional

import jubilant
import yaml

logger = logging.getLogger(__name__)


KAFKA_INTERNAL_PORT = 19093
KARAPACE_PORT = 8081
KAFKA_UI_PORT = 8080
KAFKA_UI_PROTO = "https"
CONNECT_API_PORT = 8083

CONNECT_APP_NAME = "kafka-connect"
KARAPACE_APP_NAME = "karapace"
KAFKA_UI_APP_NAME = "kafka-ui"
KAFKA_BROKER_APP_NAME = "kafka-broker"
KAFKA_CONTROLLER_APP_NAME = "kafka-controller"

CERTIFICATES_APP_NAME = "self-signed-certificates"
CORE_MODEL_NAME = "test-core"
COS_MODEL_NAME = "test-cos"
TLS_RELATION_OFFER = f"admin/{CORE_MODEL_NAME}.{CERTIFICATES_APP_NAME}"
TRAEFIK_APP_NAME = "traefik-k8s"
INGRESS_OFFER_NAME = "traefik"
COS_TERRAFORM_DIR = "tests/integration/terraform/cos"
CA_FILE = "/tmp/ca.pem"

KAFKA_UI_SECRET_KEY = "admin-password"

# Base Terraform configs
SINGLE_MODE_DEFAULT_CONFIG = {
    "profile": "testing",
    "broker": {"units": 3},
    "controller": {"units": 0},
    "connect": {"units": 1},
    "karapace": {"units": 1},
    "ui": {"units": 1},
    "integrator": {"units": 1},
}
SPLIT_MODE_DEFAULT_CONFIG = {
    "profile": "testing",
    "broker": {"units": 3},
    "controller": {"units": 3},
    "connect": {"units": 1},
    "karapace": {"units": 1},
    "ui": {"units": 1},
    "integrator": {"units": 1},
}


class TerraformDeployer:
    """Helper class to manage Terraform deployments for testing."""

    def __init__(self, model_uuid: str, terraform_dir: str = "terraform"):
        self.model_uuid = model_uuid
        self.terraform_dir = Path(terraform_dir).resolve()
        self.tfvars_file = None

    def create_tfvars(self, config: Dict[str, Any]) -> str:
        """Create a .tfvars.json file with the given configuration."""
        self.tfvars_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".tfvars.json", delete=False
        )

        # Always include model
        config["model_uuid"] = self.model_uuid

        # Write JSON content
        json.dump(config, self.tfvars_file, indent=2)

        self.tfvars_file.close()
        return self.tfvars_file.name

    def get_controller_credentials(self) -> Dict[str, str]:
        """Get Juju controller credentials for Terraform."""
        controller_credentials = yaml.safe_load(
            subprocess.check_output(
                "juju show-controller --show-password",
                stderr=subprocess.PIPE,
                shell=True,
                universal_newlines=True,
            )
        )

        def get_value(obj: dict, key: str):
            """Recursively gets value for given key in nested dict."""
            if key in obj:
                return obj.get(key, "")
            for _, v in obj.items():
                if isinstance(v, dict):
                    item = get_value(v, key)
                    if item is not None:
                        return item

        username = get_value(obj=controller_credentials, key="user")
        password = get_value(obj=controller_credentials, key="password")
        controller_addresses = ",".join(get_value(obj=controller_credentials, key="api-endpoints"))
        ca_cert = get_value(obj=controller_credentials, key="ca-cert")

        return {
            "JUJU_USERNAME": username,
            "JUJU_PASSWORD": password,
            "JUJU_CONTROLLER_ADDRESSES": controller_addresses,
            "JUJU_CA_CERT": ca_cert,
        }

    def terraform_init(self):
        """Initialize Terraform in the terraform directory."""
        result = subprocess.run(
            ["terraform", "init"], cwd=self.terraform_dir, capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Terraform init failed: {result.stderr}")

        logger.info(f"\n\nTerraform initialized:\n\n{result.stdout}")

    def terraform_apply(self, tfvars_file: str):
        """Apply Terraform configuration."""
        env = self.get_controller_credentials()
        result = subprocess.run(
            ["terraform", "apply", "-auto-approve", f"-var-file={tfvars_file}"],
            cwd=self.terraform_dir,
            text=True,
            env={**env, **dict(subprocess.os.environ)},
        )
        if result.returncode != 0:
            raise RuntimeError(f"Terraform apply failed: {result.stderr}")

        logger.info(f"\n\nTerraform applied:\n\n{result.stdout}")

    def terraform_destroy(self, tfvars_file: Optional[str] = None):
        """Destroy Terraform-managed resources."""
        env = self.get_controller_credentials()
        cmd = ["terraform", "destroy", "-auto-approve"]
        if tfvars_file:
            cmd.append(f"-var-file={tfvars_file}")

        result = subprocess.run(
            cmd,
            cwd=self.terraform_dir,
            text=True,
            env={**env, **dict(subprocess.os.environ)},
        )
        if result.returncode != 0:
            raise RuntimeError(f"Terraform destroy failed: {result.stderr}")

    def terraform_output(self) -> Dict[str, Any]:
        """Read terraform output as a JSON dict."""
        env = self.get_controller_credentials()
        result = subprocess.check_output(
            ["terraform", "output", "-json"],
            cwd=self.terraform_dir,
            text=True,
            env={**env, **dict(subprocess.os.environ)},
        )
        return json.loads(result)

    def cleanup(self):
        """Clean up temporary files."""
        if self.tfvars_file and Path(self.tfvars_file.name).exists():
            Path(self.tfvars_file.name).unlink()

        # Clean up terraform artifacts
        shutil.rmtree(self.terraform_dir / ".terraform", ignore_errors=True)
        for pattern in [".terraform.lock.hcl", "terraform.tfstate*", "*.tfplan"]:
            for file_path in self.terraform_dir.glob(pattern):
                file_path.unlink(missing_ok=True)


class COS:
    """COS application name constants."""

    ALERTMANAGER = "alertmanager"
    CATALOGUE = "catalogue"
    TRAEFIK = "traefik"
    GRAFANA = "grafana"
    LOKI = "loki"
    PROMETHEUS = "prometheus"

    APPS = [ALERTMANAGER, CATALOGUE, GRAFANA, LOKI, PROMETHEUS, TRAEFIK]


class COSAssertions:
    """Expected values for COS integration assertions."""

    APP = "kafka"
    DASHBOARDS = ["Kafka", "Kafka Connect Cluster"]
    PANELS_COUNT = 50
    PANELS_TO_CHECK = (
        "JVM",
        "Brokers Online",
        "Active Controllers",
        "Total of Topics",
    )
    ALERTS_COUNT = 25


class CosDeployer:
    """Helper class to manage COS-lite deployment for integration tests."""

    def __init__(self):
        self.cos_juju: Optional[jubilant.Juju] = None
        self.deployer: Optional[TerraformDeployer] = None

    def deploy(self, channel: str = "dev/edge") -> None:
        """Deploy COS-lite in a separate Juju model via Terraform."""
        jubilant.Juju().add_model(model=COS_MODEL_NAME)
        self.cos_juju = jubilant.Juju(model=COS_MODEL_NAME)

        # Resolve model UUID
        models = json.loads(self.cos_juju.cli("models", "--format", "json", include_model=False))
        cos_model_uuid = next(
            mdl["model-uuid"] for mdl in models["models"] if mdl["short-name"] == COS_MODEL_NAME
        )

        self.deployer = TerraformDeployer(cos_model_uuid, COS_TERRAFORM_DIR)
        self.deployer.cleanup()

        config = {"channel": channel}
        tfvars_file = self.deployer.create_tfvars(config)

        self.deployer.terraform_init()
        self.deployer.terraform_apply(tfvars_file)

    def get_cos_offers(self) -> Dict[str, str]:
        """Get COS offer URLs mapped to Kafka bundle cos_offers keys."""
        output = self.deployer.terraform_output()
        offers = output["offers"]["value"]
        return {
            "dashboard": offers["grafana_dashboards"]["url"],
            "metrics": offers["prometheus_metrics"]["url"],
            "logging": offers["loki_logging"]["url"],
        }

    def wait_for_active(self, timeout: int = 1800) -> None:
        """Wait for all COS apps to be active/idle."""
        self.cos_juju.wait(
            lambda status: all_active_idle(status, *COS.APPS),
            delay=5,
            successes=5,
            timeout=timeout,
        )

    def destroy(self) -> None:
        """Destroy COS deployment: terraform destroy first, then remove the model."""
        if self.deployer:
            try:
                self.deployer.terraform_destroy(
                    tfvars_file=self.deployer.tfvars_file.name
                    if self.deployer.tfvars_file
                    else None
                )
            except RuntimeError:
                logger.warning("Terraform destroy failed, proceeding with model removal")
            self.deployer.cleanup()

        try:
            jubilant.Juju().destroy_model(model=COS_MODEL_NAME, force=True)
        except Exception:
            logger.warning(f"Failed to destroy model {COS_MODEL_NAME}")


def deploy_core_apps(ingress: str | None = None) -> None:
    jubilant.Juju().add_model(model=CORE_MODEL_NAME)
    core_juju = jubilant.Juju(model=CORE_MODEL_NAME)
    core_juju.deploy(
        CERTIFICATES_APP_NAME, config={"ca-common-name": "test-ca"}, channel="1/stable"
    )
    apps = {CERTIFICATES_APP_NAME}

    if not ingress:
        core_juju.deploy(TRAEFIK_APP_NAME, trust=True)
        apps.add(TRAEFIK_APP_NAME)
        core_juju.integrate(CERTIFICATES_APP_NAME, f"{TRAEFIK_APP_NAME}:certificates")

    core_juju.wait(
        lambda status: all_active_idle(status, *apps),
        delay=5,
        successes=5,
        timeout=600,
    )
    core_juju.offer(f"{CORE_MODEL_NAME}.{CERTIFICATES_APP_NAME}", endpoint="certificates")

    if ingress:
        core_juju.offer(ingress)
    else:
        core_juju.offer(f"{CORE_MODEL_NAME}.{TRAEFIK_APP_NAME}", endpoint="ingress")


def get_terraform_config(
    enable_cruise_control: bool = False,
    enable_tls: bool = False,
    split_mode: bool = False,
    kafka_channel: str = "4/edge",
) -> Dict[str, Any]:
    """Get Terraform configuration based on deployment mode."""
    if split_mode:
        return get_multi_app_config(
            enable_cruise_control=enable_cruise_control,
            enable_tls=enable_tls,
            kafka_channel=kafka_channel,
        )
    else:
        return get_single_mode_config(
            enable_cruise_control=enable_cruise_control,
            enable_tls=enable_tls,
            kafka_channel=kafka_channel,
        )


def get_single_mode_config(
    enable_cruise_control: bool = False, enable_tls: bool = False, kafka_channel: str = "4/edge"
) -> Dict[str, Any]:
    """Get Terraform configuration for single-mode deployment."""
    config = SINGLE_MODE_DEFAULT_CONFIG.copy()
    if enable_tls:
        config = enable_tls_config(config)

    if enable_cruise_control:
        # Add balancer role while preserving existing roles
        config["broker"]["config"] = {"roles": "broker,balancer"}

    config["broker"] = {**config["broker"], "channel": kafka_channel}

    return config


def get_multi_app_config(
    enable_cruise_control: bool = False, enable_tls: bool = False, kafka_channel: str = "4/edge"
) -> Dict[str, Any]:
    """Get Terraform configuration for multi-app (split) mode deployment."""
    config = SPLIT_MODE_DEFAULT_CONFIG.copy()

    if enable_tls:
        config = enable_tls_config(config)

    if enable_cruise_control:
        # Add balancer role while preserving existing roles
        config["broker"]["config"] = {"roles": "broker,balancer"}

    config["broker"] = {**config["broker"], "channel": kafka_channel}
    config["controller"] = {**config["controller"], "channel": kafka_channel}

    return config


def enable_tls_config(base_config: Dict[str, Any]) -> Dict[str, Any]:
    """Modify configuration to enable TLS across all components."""
    tls_config = base_config.copy()

    # For TLS testing, we'll need to add TLS offer
    # This would typically come from a TLS certificates operator
    tls_config["tls_offer"] = TLS_RELATION_OFFER

    return tls_config


def get_secret_by_label(model: str, label: str, owner: str) -> dict[str, str]:
    secrets_meta_raw = subprocess.check_output(
        f"JUJU_MODEL={model} juju list-secrets --format json",
        stderr=subprocess.PIPE,
        shell=True,
        universal_newlines=True,
    ).strip()
    secrets_meta = json.loads(secrets_meta_raw)

    for secret_id in secrets_meta:
        if owner and not secrets_meta[secret_id]["owner"] == owner:
            continue
        if secrets_meta[secret_id]["label"] == label:
            break

    secrets_data_raw = subprocess.check_output(
        f"JUJU_MODEL={model} juju show-secret --format json --reveal {secret_id}",
        stderr=subprocess.PIPE,
        shell=True,
        universal_newlines=True,
    )

    secret_data = json.loads(secrets_data_raw)
    return secret_data[secret_id]["content"]["Data"]


def check_socket(host: str | None, port: int) -> bool:
    """Checks whether IPv4 socket is up or not."""
    if host is None:
        return False

    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex((host, port)) == 0


def all_active_idle(status: jubilant.Status, *apps: str):
    """Helper function for jubilant all units active|idle checks."""
    return jubilant.all_agents_idle(status, *apps) and jubilant.all_active(status, *apps)


def get_app_list(kraft_mode):
    """Get the list of expected applications based on kraft_mode."""
    base_apps = [KAFKA_UI_APP_NAME, KARAPACE_APP_NAME, CONNECT_APP_NAME, KAFKA_BROKER_APP_NAME]
    return base_apps + ([KAFKA_CONTROLLER_APP_NAME] if kraft_mode == "multi" else [])
