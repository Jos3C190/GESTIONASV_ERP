# ==============================================================================
# GESTIONASV ERP — MÓDULO DE SEGURIDAD (SECURITY GROUPS ENCADENADOS)
# Principio de Menor Privilegio (Zero Trust Perimetral)
# ==============================================================================

# 1. Security Group del Application Load Balancer (Público hacia Internet)
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-${var.environment}-alb-sg"
  description = "Permite trafico HTTP/HTTPS publico hacia el Load Balancer"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP desde cualquier origen"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS desde cualquier origen"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Salida hacia las tareas de ECS"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-alb-sg"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# 2. Security Group de las Tareas ECS Fargate (Solo acepta tráfico del ALB)
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.project_name}-${var.environment}-ecs-task-sg"
  description = "Aislamiento estricto: solo acepta trafico proveniente del ALB"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Trafico Frontend SvelteKit (:3000) solo desde el ALB"
    from_port       = 3000
    to_port         = 3000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description     = "Trafico Backend FastAPI (:8000) solo desde el ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Salida a Internet para descargar imagenes de ECR y consultar Secrets Manager / Bedrock"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-ecs-task-sg"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# 3. Security Group de la Base de Datos RDS (Solo acepta tráfico de ECS)
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-${var.environment}-rds-sg"
  description = "Aislamiento estricto: solo acepta conexiones PostgreSQL desde ECS"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL (:5432) exclusivamente desde las tareas de ECS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    description = "Sin salida requerida"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-rds-sg"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}
