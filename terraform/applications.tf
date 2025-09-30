resource "juju_application" "integrator" {
  model = var.model
  name  = var.integrator.app_name
  units = var.integrator.units

  charm {
    name     = "data-integrator"
    channel  = var.integrator.channel
    revision = var.integrator.revision
    base     = var.integrator.base
  }

  config = var.integrator.config
}
