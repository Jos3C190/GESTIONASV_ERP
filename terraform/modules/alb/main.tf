# ==============================================================================
# GESTIONASV ERP — MÓDULO DE APPLICATION LOAD BALANCER (ALB)
# Enrutamiento basado en Path (/api/* hacia Backend, /* hacia Frontend)
# ==============================================================================

resource "aws_lb" "main" {
  name               = "${var.project_name}-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = false

  tags = {
    Name        = "${var.project_name}-${var.environment}-alb"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# 1. Target Group para el Frontend SvelteKit (:3000)
# IMPORTANTE: target_type = "ip" obligatorio para modo de red awsvpc en Fargate
resource "aws_lb_target_group" "frontend" {
  name        = "${var.project_name}-${var.environment}-tg-front"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/"
    port                = "3000"
    protocol            = "HTTP"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200-399"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-tg-frontend"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# 2. Target Group para el Backend FastAPI (:8000)
# IMPORTANTE: target_type = "ip" obligatorio para modo de red awsvpc en Fargate
resource "aws_lb_target_group" "backend" {
  name        = "${var.project_name}-${var.environment}-tg-back"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/health"
    port                = "8000"
    protocol            = "HTTP"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-tg-backend"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# 3. Listener HTTP (Puerto 80) — Acción por defecto: reenviar a Frontend
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

# 4. Regla de Enrutamiento por Path: /api/* hacia el Backend FastAPI
resource "aws_lb_listener_rule" "api_routing" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/api/*", "/docs", "/openapi.json"]
    }
  }
}
