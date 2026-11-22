variable "aws_region" {
  type        = string
  description = "Región de AWS donde se aprovisionan los recursos"
  default     = "us-east-1"
}

variable "project_name" {
  type        = string
  description = "Nombre identificador del proyecto"
  default     = "gestiona-erp"
}

variable "environment" {
  type        = string
  description = "Ambiente de despliegue (dev, staging, prod)"
  default     = "staging"
}

# Configuración de Red
variable "vpc_cidr" {
  type        = string
  description = "Bloque CIDR de la VPC"
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  type        = list(string)
  description = "Zonas de disponibilidad en la región"
  default     = ["us-east-1a", "us-east-1b"]
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Subredes públicas para ALB y tareas Fargate"
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "Subredes privadas para Amazon RDS PostgreSQL"
  default     = ["10.0.10.0/24", "10.0.20.0/24"]
}

# Configuración de Base de Datos
variable "db_instance_class" {
  type        = string
  description = "Clase de instancia para RDS (db.t3.micro o db.t4g.micro)"
  default     = "db.t3.micro"
}

variable "db_name" {
  type        = string
  description = "Nombre de la base de datos PostgreSQL inicial"
  default     = "gestionasv_erp"
}

variable "db_username" {
  type        = string
  description = "Usuario administrador de RDS"
  default     = "erp_admin"
}

variable "db_password" {
  type        = string
  description = "Contraseña maestra de RDS"
  sensitive   = true
  default     = "GestionaERP2026SecurePass!"
}

# Configuración de Contenedores ECS Fargate
variable "frontend_image" {
  type        = string
  description = "URI de la imagen de ECR para SvelteKit"
  default     = "123456789012.dkr.ecr.us-east-1.amazonaws.com/gestiona-erp-frontend:latest"
}

variable "backend_image" {
  type        = string
  description = "URI de la imagen de ECR para FastAPI"
  default     = "123456789012.dkr.ecr.us-east-1.amazonaws.com/gestiona-erp-backend:latest"
}

variable "fargate_cpu" {
  type        = string
  description = "CPU asignada a la tarea (512 = 0.5 vCPU)"
  default     = "512"
}

variable "fargate_memory" {
  type        = string
  description = "Memoria RAM asignada a la tarea (1024 = 1 GB)"
  default     = "1024"
}

variable "desired_count" {
  type        = number
  description = "Cantidad de tareas Fargate concurrentes"
  default     = 1
}

variable "db_secret_arn" {
  type        = string
  description = "ARN opcional de Secrets Manager para inyectar credenciales"
  default     = ""
}
