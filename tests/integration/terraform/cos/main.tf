# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

module "cos-lite" {
  source       = "git::https://github.com/canonical/observability-stack//terraform/cos-lite?ref=track/3.0"
  model        = { uuid = var.model_uuid }
  risk         = var.risk
  internal_tls = var.internal_tls
}
