output "alb_arn" {
  description = "ARN del Application Load Balancer"
  value       = aws_lb.main.arn
}

output "alb_dns_name" {
  description = "Nombre DNS público del Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Canonical Hosted Zone ID del ALB (para Route 53)"
  value       = aws_lb.main.zone_id
}

output "frontend_target_group_arn" {
  description = "ARN del Target Group del Frontend"
  value       = aws_lb_target_group.frontend.arn
}

output "backend_target_group_arn" {
  description = "ARN del Target Group del Backend"
  value       = aws_lb_target_group.backend.arn
}
