output "alb_security_group_id" {
  description = "ID del Security Group del ALB"
  value       = aws_security_group.alb.id
}

output "ecs_tasks_security_group_id" {
  description = "ID del Security Group de las tareas ECS"
  value       = aws_security_group.ecs_tasks.id
}

output "rds_security_group_id" {
  description = "ID del Security Group de Amazon RDS"
  value       = aws_security_group.rds.id
}
