# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

module "cos-lite" {
  source       = "git::https://github.com/canonical/observability-stack//terraform/cos-lite?ref=main"
  model_uuid   = var.model_uuid
  channel      = var.channel
  internal_tls = var.internal_tls
}
