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

variable "vpc_cidr" {
  type        = string
  description = "Bloque CIDR de la VPC"
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  type        = list(string)
  description = "Zonas de disponibilidad para alta disponibilidad"
  default     = ["us-east-1a", "us-east-1b"]
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Bloques CIDR para las subredes públicas"
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "Bloques CIDR para las subredes privadas"
  default     = ["10.0.10.0/24", "10.0.20.0/24"]
}
