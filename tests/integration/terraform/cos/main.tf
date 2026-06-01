# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

module "cos-lite" {
  source       = "git::https://github.com/canonical/observability-stack//terraform/cos-lite?ref=429fbe7cef454fe33596d5c918405d719a807a38"
  model_uuid   = var.model_uuid
  risk         = var.risk
  internal_tls = var.internal_tls
}
