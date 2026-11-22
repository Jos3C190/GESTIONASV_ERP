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

variable "aws_region" {
  type        = string
  description = "Región de AWS"
  default     = "us-east-1"
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Subredes públicas para las tareas de Fargate"
}

variable "ecs_tasks_security_group_id" {
  type        = string
  description = "Security Group de las tareas ECS"
}

variable "frontend_target_group_arn" {
  type        = string
  description = "Target Group ARN para el Frontend"
}

variable "backend_target_group_arn" {
  type        = string
  description = "Target Group ARN para el Backend"
}

variable "frontend_image" {
  type        = string
  description = "URI de la imagen de ECR para el Frontend"
  default     = "public.ecr.aws/dummy/gestiona-erp-frontend:latest"
}

variable "backend_image" {
  type        = string
  description = "URI de la imagen de ECR para el Backend"
  default     = "public.ecr.aws/dummy/gestiona-erp-backend:latest"
}

variable "fargate_cpu" {
  type        = string
  description = "vCPU asignada a la tarea (256 = 0.25 vCPU, 512 = 0.5 vCPU)"
  default     = "512"
}

variable "fargate_memory" {
  type        = string
  description = "Memoria RAM asignada a la tarea en MB (1024 = 1 GB)"
  default     = "1024"
}

variable "desired_count" {
  type        = number
  description = "Número deseado de tareas Fargate en ejecución"
  default     = 1
}

variable "db_secret_arn" {
  type        = string
  description = "ARN del secreto de Secrets Manager con la URL de base de datos"
  default     = ""
}
