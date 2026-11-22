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
  description = "ID de la VPC"
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "IDs de subredes públicas para alojar el ALB"
}

variable "alb_security_group_id" {
  type        = string
  description = "ID del Security Group para el ALB"
}
