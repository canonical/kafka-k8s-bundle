# Integrations between Kafka products

resource "juju_integration" "kafka_kraft" {
  count      = local.deployment_mode == "split" ? 1 : 0
  model_uuid = var.model_uuid

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
  count      = var.connect.units > 0 ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.broker.app_name
    endpoint = "kafka-client"
  }

  application {
    name = module.connect[0].app_name
  }
}

resource "juju_integration" "kafka_karapace" {
  count      = var.karapace.units > 0 ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.broker.app_name
    endpoint = "kafka-client"
  }

  application {
    name = module.karapace[0].app_name
  }
}

resource "juju_integration" "kafka_ui" {
  count      = var.ui.units > 0 ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.broker.app_name
    endpoint = "kafka-client"
  }

  application {
    name = module.ui[0].app_name
  }
}


resource "juju_integration" "karapace_ui" {
  count      = var.karapace.units > 0 && var.ui.units > 0 ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.karapace[0].app_name
    endpoint = "karapace"
  }

  application {
    name = module.ui[0].app_name
  }
}

resource "juju_integration" "kafka_connect_ui" {
  count      = var.connect.units > 0 && var.ui.units > 0 ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.connect[0].app_name
    endpoint = "connect-client"
  }

  application {
    name = module.ui[0].app_name
  }
}

resource "juju_integration" "integrator_kafka" {
  model_uuid = var.model_uuid

  application {
    name = juju_application.integrator.name
  }

  application {
    name = module.broker.app_name
  }
}

# TLS Integrations

resource "juju_integration" "kafka_tls" {
  count      = local.tls_enabled ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.broker.app_name
    endpoint = "certificates"
  }

  application {
    offer_url = var.tls_offer
  }
}

resource "juju_integration" "kafka_connect_tls" {
  count      = local.tls_enabled && var.connect.units > 0 ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.connect[0].app_name
    endpoint = "certificates"
  }

  application {
    offer_url = var.tls_offer
  }
}

resource "juju_integration" "karapace_tls" {
  count      = local.tls_enabled && var.karapace.units > 0 ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.karapace[0].app_name
    endpoint = "certificates"
  }

  application {
    offer_url = var.tls_offer
  }
}

resource "juju_integration" "kafka_ui_ingress" {
  count      = var.ingress_offer != null && var.ui.units > 0 ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.ui[0].app_name
    endpoint = "ingress"
  }

  application {
    offer_url = var.ingress_offer
  }
}

# OAuth Integrations

resource "juju_integration" "kafka_oauth" {
  count      = local.oauth_enabled ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.broker.app_name
    endpoint = "oauth"
  }

  application {
    offer_url = var.oauth_offer
  }
}

resource "juju_integration" "kafka_ui_oauth" {
  count      = local.oauth_enabled && var.ui.units > 0 ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.ui[0].app_name
    endpoint = "oauth"
  }

  application {
    offer_url = var.oauth_offer
  }
}

# COS Integrations

# Integration of the opentelemetry-collector with the offers from COS
resource "juju_integration" "otel_cos_metrics" {
  count      = local.cos_enabled ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = juju_application.kafka_cos_agent[0].name
    endpoint = "send-remote-write"
  }

  application {
    offer_url = var.cos_offers.metrics
  }
}

resource "juju_integration" "otel_cos_dashboard" {
  count      = local.cos_enabled ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = juju_application.kafka_cos_agent[0].name
    endpoint = "grafana-dashboards-provider"
  }

  application {
    offer_url = var.cos_offers.dashboard
  }
}

resource "juju_integration" "otel_cos_logging" {
  count      = local.cos_enabled ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = juju_application.kafka_cos_agent[0].name
    endpoint = "send-loki-logs"
  }

  application {
    offer_url = var.cos_offers.logging
  }
}

# Integrations of the Kafka applications with opentelemetry-collector-k8s
resource "juju_integration" "kafka_cos_metrics" {
  count      = local.cos_enabled ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.broker.app_name
    endpoint = "metrics-endpoint"
  }

  application {
    name = juju_application.kafka_cos_agent[0].name
  }

}

resource "juju_integration" "kafka_cos_dashboard" {
  count      = local.cos_enabled ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.broker.app_name
    endpoint = "grafana-dashboard"
  }

  application {
    name     = juju_application.kafka_cos_agent[0].name
    endpoint = "grafana-dashboards-consumer"
  }

}

resource "juju_integration" "kafka_cos_logging" {
  count      = local.cos_enabled ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.broker.app_name
    endpoint = "logging"
  }

  application {
    name     = juju_application.kafka_cos_agent[0].name
    endpoint = "receive-loki-logs"
  }

}

resource "juju_integration" "kraft_cos_metrics" {
  count      = local.cos_enabled && local.deployment_mode == "split" ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.controller[0].app_name
    endpoint = "metrics-endpoint"
  }

  application {
    name = juju_application.kafka_cos_agent[0].name
  }

}

resource "juju_integration" "kraft_cos_dashboard" {
  count      = local.cos_enabled && local.deployment_mode == "split" ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.controller[0].app_name
    endpoint = "grafana-dashboard"
  }

  application {
    name     = juju_application.kafka_cos_agent[0].name
    endpoint = "grafana-dashboards-consumer"
  }

}

resource "juju_integration" "kraft_cos_logging" {
  count      = local.cos_enabled && local.deployment_mode == "split" ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.controller[0].app_name
    endpoint = "logging"
  }

  application {
    name     = juju_application.kafka_cos_agent[0].name
    endpoint = "receive-loki-logs"
  }

}

resource "juju_integration" "connect_cos_metrics" {
  count      = local.cos_enabled && var.connect.units > 0 ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.connect[0].app_name
    endpoint = "metrics-endpoint"
  }

  application {
    name = juju_application.kafka_cos_agent[0].name
  }

}

resource "juju_integration" "connect_cos_dashboard" {
  count      = local.cos_enabled && var.connect.units > 0 ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.connect[0].app_name
    endpoint = "grafana-dashboard"
  }

  application {
    name     = juju_application.kafka_cos_agent[0].name
    endpoint = "grafana-dashboards-consumer"
  }

}

resource "juju_integration" "connect_cos_logging" {
  count      = local.cos_enabled && var.connect.units > 0 ? 1 : 0
  model_uuid = var.model_uuid

  application {
    name     = module.connect[0].app_name
    endpoint = "logging"
  }

  application {
    name     = juju_application.kafka_cos_agent[0].name
    endpoint = "receive-loki-logs"
  }

}