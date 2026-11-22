output "alb_public_url" {
  description = "URL pública de acceso al ERP a través del Application Load Balancer"
  value       = "http://${module.alb.alb_dns_name}"
}

output "api_documentation_url" {
  description = "URL pública de la documentación interactiva Swagger de FastAPI"
  value       = "http://${module.alb.alb_dns_name}/docs"
}

output "rds_endpoint" {
  description = "Endpoint privado de conexión a la base de datos PostgreSQL"
  value       = module.database.db_endpoint
}

output "ecs_cluster_name" {
  description = "Nombre del clúster de ECS Fargate"
  value       = module.ecs.cluster_name
}

output "ecs_service_name" {
  description = "Nombre del servicio de ECS Fargate"
  value       = module.ecs.service_name
}
