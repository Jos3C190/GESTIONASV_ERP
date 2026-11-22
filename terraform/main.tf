# ==============================================================================
# GESTIONASV ERP — PLATFORM ENGINEERING GOLDEN PATH (TERRAFORM ROOT)
# Orquestación declarativa de la arquitectura completa en AWS
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      Platform    = "Platform-Engineering-IaC"
      ManagedBy   = "Terraform"
    }
  }
}

# 1. Módulo de Red (VPC, Subredes Públicas y Privadas en 2 AZs)
module "networking" {
  source = "./modules/networking"

  project_name         = var.project_name
  environment          = var.environment
  vpc_cidr             = var.vpc_cidr
  availability_zones   = var.availability_zones
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
}

# 2. Módulo de Seguridad (Security Groups Encadenados con Menor Privilegio)
module "security" {
  source = "./modules/security"

  project_name = var.project_name
  environment  = var.environment
  vpc_id       = module.networking.vpc_id
}

# 3. Módulo de Application Load Balancer (Enrutamiento por Path)
module "alb" {
  source = "./modules/alb"

  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.networking.vpc_id
  public_subnet_ids     = module.networking.public_subnet_ids
  alb_security_group_id = module.security.alb_security_group_id
}

# 4. Módulo de Base de Datos (Amazon RDS PostgreSQL en Subred Privada)
module "database" {
  source = "./modules/database"

  project_name          = var.project_name
  environment           = var.environment
  private_subnet_ids    = module.networking.private_subnet_ids
  rds_security_group_id = module.security.rds_security_group_id
  instance_class        = var.db_instance_class
  db_name               = var.db_name
  db_username           = var.db_username
  db_password           = var.db_password
  skip_final_snapshot   = var.environment != "prod"
  deletion_protection   = var.environment == "prod"
}

# 5. Módulo de Cómputo (Amazon ECS Fargate Serverless con Dual-Container)
module "ecs" {
  source = "./modules/ecs"

  project_name                = var.project_name
  environment                 = var.environment
  aws_region                  = var.aws_region
  public_subnet_ids           = module.networking.public_subnet_ids
  ecs_tasks_security_group_id = module.security.ecs_tasks_security_group_id
  frontend_target_group_arn   = module.alb.frontend_target_group_arn
  backend_target_group_arn    = module.alb.backend_target_group_arn
  frontend_image              = var.frontend_image
  backend_image               = var.backend_image
  fargate_cpu                 = var.fargate_cpu
  fargate_memory              = var.fargate_memory
  desired_count               = var.desired_count
  db_secret_arn               = var.db_secret_arn
}
