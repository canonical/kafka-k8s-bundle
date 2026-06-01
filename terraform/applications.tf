resource "juju_application" "integrator" {
  model_uuid = var.model_uuid
  name       = var.integrator.app_name
  units      = var.integrator.units

  charm {
    name     = "data-integrator"
    channel  = var.integrator.channel
    revision = var.integrator.revision
    base     = var.integrator.base
  }

  config = var.integrator.config
}

resource "juju_application" "kafka_cos_agent" {
  count      = local.cos_enabled ? 1 : 0
  model_uuid = var.model_uuid
  name       = "opentelemetry-collector"

  charm {
    name    = local.cos_agent_charm
    channel = local.cos_agent_channel
    base    = var.broker.base
  }
}
