# ==============================================================================
# GESTIONASV ERP — CONFIGURACIÓN DE ESTADO REMOTO SEGURO (S3 + DYNAMODB)
# Buenas Prácticas de Platform Engineering: Cifrado en Reposo y Bloqueo de Estado
# ==============================================================================

# Para habilitar el backend remoto en producción, descomentar este bloque
# después de crear el bucket S3 y la tabla DynamoDB en la cuenta de AWS:

# terraform {
#   backend "s3" {
#     bucket         = "gestiona-erp-terraform-state-us-east-1"
#     key            = "platform/staging/terraform.tfstate"
#     region         = "us-east-1"
#     encrypt        = true
#     dynamodb_table = "gestiona-erp-terraform-locks"
#   }
# }
