# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

# COS-lite is a Kubernetes-only stack. As the Charmed Apache Kafka K8s bundle is
# also deployed on a Kubernetes cloud, both can share the same Juju controller.
# This module deploys COS-lite into its own model and exposes the offers required
# for cross-model integration with the Kafka applications.

module "cos-lite" {
  source       = "git::https://github.com/canonical/observability-stack//terraform/cos-lite?ref=429fbe7cef454fe33596d5c918405d719a807a38"
  model_uuid   = var.model_uuid
  risk         = var.risk
  internal_tls = var.internal_tls
}
