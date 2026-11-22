output "db_endpoint" {
  description = "Endpoint de conexión de la base de datos (host:port)"
  value       = aws_db_instance.main.endpoint
}

output "db_address" {
  description = "Dirección host de la base de datos"
  value       = aws_db_instance.main.address
}

output "db_port" {
  description = "Puerto de PostgreSQL"
  value       = aws_db_instance.main.port
}

output "db_name" {
  description = "Nombre de la base de datos"
  value       = aws_db_instance.main.db_name
}
