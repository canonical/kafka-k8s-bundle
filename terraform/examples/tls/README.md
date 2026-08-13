# Full Apache Kafka K8s Bundle + TLS

This is an example deployment which deploys the Charmed Apache Kafka K8s bundle alongside the self-signed certificates TLS provider, which enables TLS on all client relations.

To deploy this example, following commands can be used:

```bash
terraform init

terraform apply -target module.tls
terraform apply
```
