#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests both single-mode and multi-app mode deployments with all components."""

import logging

from jubilant import Juju
from tests.integration.terraform.component_validation import ComponentValidation
from tests.integration.terraform.helpers import all_active_idle, deploy_core_apps, get_app_list

logger = logging.getLogger(__name__)


def test_deploy_core_model(request):
    """Deploy the ingress and TLS provider charms."""
    provided_ingress = f'{request.config.getoption("--ingress-offer")}'
    deploy_core_apps(ingress=provided_ingress)


def test_deployment_active(juju: Juju, kraft_mode, deploy_cluster):
    """Test that Kafka is deployed and active."""
    # Fixtures will deploy using terraform
    # Wait for all applications to be active
    app_list = get_app_list(kraft_mode)
    juju.wait(
        lambda status: all_active_idle(status, *app_list),
        delay=3,
        successes=20,
        timeout=3600,
    )
    status = juju.status()
    for app in app_list:
        assert status.apps[app].app_status.current == "active"


def test_components(juju: Juju):
    """Test that all components are deployed."""
    validator = ComponentValidation(juju=juju)

    validator.test_kafka_admin_operations()
    validator.test_kafka_producer_consumer()
    validator.test_karapace()
    validator.test_ui_accessibility()
    validator.test_connect_endpoints()
    validator.test_create_mm2_connector()


def test_tls_toggle(juju: Juju, kraft_mode, enable_terraform_tls):
    """Test enabling and disabling TLS across the cluster."""
    app_list = get_app_list(kraft_mode)

    juju.wait(
        lambda status: all_active_idle(status, *app_list),
        delay=3,
        successes=20,
        timeout=3600,
    )
    status = juju.status()
    for app in app_list:
        assert status.apps[app].app_status.current == "active"


def test_tls_components(juju: Juju):
    """Test that all components work with TLS enabled."""
    validator = ComponentValidation(juju=juju, tls=True)

    validator.test_kafka_admin_operations()
    validator.test_kafka_producer_consumer()
    # FIXME: enable Karapace tests when the TLS toggle issue is fixes
    # validator.test_karapace()
    validator.test_ui_accessibility()
    validator.test_connect_endpoints()
    validator.test_create_mm2_connector()
