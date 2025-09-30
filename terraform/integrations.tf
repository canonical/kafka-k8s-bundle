# Integrations between Kafka products

resource "juju_integration" "kafka_kraft" {
  count = local.deployment_mode == "split" ? 1 : 0
  model = var.model

  application {
    name     = module.broker.app_name
    endpoint = "peer-cluster-orchestrator"
  }

  application {
    name     = module.controller[0].app_name
    endpoint = "peer-cluster"
  }
}

resource "juju_integration" "kafka_connect" {
  count = var.connect.units > 0 ? 1 : 0
  model = var.model

  application {
    name     = module.broker.app_name
    endpoint = "kafka-client"
  }

  application {
    name = module.connect[0].app_name
  }
}

resource "juju_integration" "kafka_karapace" {
  count = var.karapace.units > 0 ? 1 : 0
  model = var.model

  application {
    name     = module.broker.app_name
    endpoint = "kafka-client"
  }

  application {
    name = module.karapace[0].app_name
  }
}

resource "juju_integration" "kafka_ui" {
  count = var.ui.units > 0 ? 1 : 0
  model = var.model

  application {
    name     = module.broker.app_name
    endpoint = "kafka-client"
  }

  application {
    name = module.ui[0].app_name
  }
}


resource "juju_integration" "karapace_ui" {
  count = var.karapace.units > 0 && var.ui.units > 0 ? 1 : 0
  model = var.model

  application {
    name     = module.karapace[0].app_name
    endpoint = "karapace"
  }

  application {
    name = module.ui[0].app_name
  }
}

resource "juju_integration" "kafka_connect_ui" {
  count = var.connect.units > 0 && var.ui.units > 0 ? 1 : 0
  model = var.model

  application {
    name     = module.connect[0].app_name
    endpoint = "connect-client"
  }

  application {
    name = module.ui[0].app_name
  }
}

resource "juju_integration" "integrator_kafka" {
  model = var.model

  application {
    name = juju_application.integrator.name
  }

  application {
    name = module.broker.app_name
  }
}

# TLS Integrations

resource "juju_integration" "kafka_tls" {
  count = local.tls_enabled ? 1 : 0
  model = var.model

  application {
    name     = module.broker.app_name
    endpoint = "certificates"
  }

  application {
    offer_url = var.tls_offer
  }
}

resource "juju_integration" "kafka_connect_tls" {
  count = local.tls_enabled && var.connect.units > 0 ? 1 : 0
  model = var.model

  application {
    name     = module.connect[0].app_name
    endpoint = "certificates"
  }

  application {
    offer_url = var.tls_offer
  }
}

resource "juju_integration" "karapace_tls" {
  count = local.tls_enabled && var.karapace.units > 0 ? 1 : 0
  model = var.model

  application {
    name     = module.karapace[0].app_name
    endpoint = "certificates"
  }

  application {
    offer_url = var.tls_offer
  }
}

resource "juju_integration" "kafka_ui_ingress" {
  count = var.ingress_offer != null && var.ui.units > 0 ? 1 : 0
  model = var.model

  application {
    name     = module.ui[0].app_name
    endpoint = "ingress"
  }

  application {
    offer_url = var.ingress_offer
  }
}

# COS Integrations 

resource "juju_integration" "kafka_cos_metrics" {
  count = local.cos_enabled ? 1 : 0
  model = var.model

  application {
    name     = module.broker.app_name
    endpoint = "metrics-endpoint"
  }

  application {
    offer_url = var.cos_offers.metrics
  }

}

resource "juju_integration" "kafka_cos_dashboard" {
  count = local.cos_enabled ? 1 : 0
  model = var.model

  application {
    name     = module.broker.app_name
    endpoint = "grafana-dashboard"
  }

  application {
    offer_url = var.cos_offers.dashboard
  }

}

resource "juju_integration" "kafka_cos_logging" {
  count = local.cos_enabled ? 1 : 0
  model = var.model

  application {
    name     = module.broker.app_name
    endpoint = "logging"
  }

  application {
    offer_url = var.cos_offers.logging
  }

}

resource "juju_integration" "kraft_cos_metrics" {
  count = local.cos_enabled && local.deployment_mode == "split" ? 1 : 0
  model = var.model

  application {
    name     = module.controller[0].app_name
    endpoint = "metrics-endpoint"
  }

  application {
    offer_url = var.cos_offers.metrics
  }

}

resource "juju_integration" "kraft_cos_dashboard" {
  count = local.cos_enabled && local.deployment_mode == "split" ? 1 : 0
  model = var.model

  application {
    name     = module.controller[0].app_name
    endpoint = "grafana-dashboard"
  }

  application {
    offer_url = var.cos_offers.dashboard
  }

}

resource "juju_integration" "kraft_cos_logging" {
  count = local.cos_enabled && local.deployment_mode == "split" ? 1 : 0
  model = var.model

  application {
    name     = module.controller[0].app_name
    endpoint = "logging"
  }

  application {
    offer_url = var.cos_offers.logging
  }

}

resource "juju_integration" "connect_cos_metrics" {
  count = local.cos_enabled && var.connect.units > 0 ? 1 : 0
  model = var.model

  application {
    name     = module.connect[0].app_name
    endpoint = "metrics-endpoint"
  }

  application {
    offer_url = var.cos_offers.metrics
  }

}

resource "juju_integration" "connect_cos_dashboard" {
  count = local.cos_enabled && var.connect.units > 0 ? 1 : 0
  model = var.model

  application {
    name     = module.connect[0].app_name
    endpoint = "grafana-dashboard"
  }

  application {
    offer_url = var.cos_offers.dashboard
  }

}

resource "juju_integration" "connect_cos_logging" {
  count = local.cos_enabled && var.connect.units > 0 ? 1 : 0
  model = var.model

  application {
    name     = module.connect[0].app_name
    endpoint = "logging"
  }

  application {
    offer_url = var.cos_offers.logging
  }

}