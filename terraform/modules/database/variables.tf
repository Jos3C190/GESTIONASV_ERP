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

variable "private_subnet_ids" {
  type        = list(string)
  description = "Subredes privadas para el DB Subnet Group"
}

variable "rds_security_group_id" {
  type        = string
  description = "ID del Security Group para PostgreSQL"
}

variable "postgres_version" {
  type        = string
  description = "Versión de PostgreSQL"
  default     = "16.3"
}

variable "instance_class" {
  type        = string
  description = "Tipo de instancia de RDS (FinOps: db.t3.micro o db.t4g.micro)"
  default     = "db.t3.micro"
}

variable "allocated_storage" {
  type        = number
  description = "Almacenamiento inicial en GB"
  default     = 20
}

variable "max_allocated_storage" {
  type        = number
  description = "Límite máximo de autoscaling de almacenamiento en GB"
  default     = 50
}

variable "db_name" {
  type        = string
  description = "Nombre de la base de datos inicial"
  default     = "gestionasv_erp"
}

variable "db_username" {
  type        = string
  description = "Usuario administrador de la base de datos"
  default     = "erp_admin"
}

variable "db_password" {
  type        = string
  description = "Contraseña maestra de PostgreSQL (en producción viene de Secrets Manager)"
  sensitive   = true
}

variable "backup_retention_period" {
  type        = number
  description = "Días de retención de copias de seguridad automáticas"
  default     = 7
}

variable "skip_final_snapshot" {
  type        = bool
  description = "Omitir snapshot final al destruir (true para dev/staging, false para prod)"
  default     = true
}

variable "deletion_protection" {
  type        = bool
  description = "Protección contra eliminación accidental"
  default     = false
}
