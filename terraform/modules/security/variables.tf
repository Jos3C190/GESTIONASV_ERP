variable "project_name" {
  type        = string
  description = "Nombre base del proyecto"
  default     = "gestiona-erp"
}

variable "environment" {
  type        = string
  description = "Entorno de despliegue (dev, staging, prod)"
  default     = "staging"
}

variable "vpc_id" {
  type        = string
  description = "ID de la VPC donde residen los Security Groups"
}
