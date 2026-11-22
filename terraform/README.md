# 🏗️ GESTIONASV ERP — Platform Engineering & Infrastructure as Code (IaC)

Este directorio contiene la arquitectura completa de infraestructura declarativa para el sistema **GESTIONASV ERP** en **Amazon Web Services (AWS)**, diseñada bajo los principios del **AWS Well-Architected Framework** y las prácticas modernas de **Platform Engineering**.

---

## 📐 Topología de Arquitectura

```
                        Internet (Usuarios)
                                │
                                ▼ [Puerto 80 / 443]
              ┌─────────────────────────────────────┐
              │     Application Load Balancer       │  (Subredes Públicas Multi-AZ)
              │    (Enrutamiento por Path)          │
              └───────────────┬─────────────────────┘
                              │
                    ┌─────────┴─────────┐
         /api/* ────┤                   ├──── /* (Web)
                    ▼                   ▼
            [TG: Backend :8000] [TG: Frontend :3000]
                    │                   │
                    └─────────┬─────────┘
                              ▼ awsvpc (IP privada de la tarea)
              ┌─────────────────────────────────────┐
              │      Amazon ECS con AWS Fargate     │  (Subredes Públicas con SG blindado)
              │  ┌───────────────────────────────┐  │
              │  │  SvelteKit (:3000) Frontend   │  │
              │  ├───────────────────────────────┤  │
              │  │  FastAPI (:8000) Backend      │  │
              │  └───────────────┬───────────────┘  │
              └──────────────────┼──────────────────┘
                                 │
                                 ▼ [Puerto 5432 - Solo desde ECS SG]
              ┌─────────────────────────────────────┐
              │     Amazon RDS PostgreSQL (gp3)     │  (Subredes Privadas Multi-AZ)
              │       (Sin acceso a Internet)       │
              └─────────────────────────────────────┘
```

---

## 🧩 Módulos Diseñados

| Módulo | Ruta | Propósito Técnico |
|---|---|---|
| **Networking** | `modules/networking` | VPC con soporte DNS, Internet Gateway, 2 subredes públicas y 2 subredes privadas distribuidas en `us-east-1a` y `us-east-1b`. |
| **Security** | `modules/security` | Security Groups encadenados bajo el principio de menor privilegio: el ALB recibe tráfico público; las tareas de ECS solo aceptan tráfico del ALB; y PostgreSQL solo acepta conexiones de la tarea ECS. |
| **ALB** | `modules/alb` | Application Load Balancer con Target Groups de tipo `ip` para compatibilidad con Fargate `awsvpc`, con enrutamiento de `/api/*` y `/docs` hacia FastAPI y `/*` hacia SvelteKit. |
| **ECS Fargate** | `modules/ecs` | Clúster ECS con Container Insights, Grupo de logs en CloudWatch con retención de 14 días, roles IAM de ejecución y tarea (con acceso a Bedrock Guardrails), y Task Definition dual-container con Rolling Updates (`min: 100%`, `max: 200%`). |
| **Database** | `modules/database` | DB Subnet Group en subredes privadas, instancia RDS PostgreSQL `db.t3.micro` con almacenamiento gp3 cifrado con KMS, copias de seguridad automáticas y protección de eliminación opcional. |

---

## 🎯 Alineación con el AWS Well-Architected Framework

Esta implementación resuelve directamente las recomendaciones de 4 pilares fundamentales:

1. **Excelencia Operativa (OPS 05 - Implement change with IaC):**
   * Eliminación del despliegue artesanal por consola o scripts sueltos.
   * La infraestructura se versiona en Git, permitiendo auditoría, previsualización de cambios (`terraform plan`) y reversión instantánea.
2. **Seguridad (SEC 02 - Secure network boundaries & least privilege):**
   * Aislamiento perimetral: la base de datos PostgreSQL no posee dirección IP pública y solo responde al Security Group de los contenedores.
   * Separación de privilegios en IAM: el *Execution Role* solo baja imágenes y lee secretos; el *Task Role* solo invoca modelos y Guardrails de Amazon Bedrock.
3. **Confiabilidad (REL 08 - Design interactions to prevent failures):**
   * Despliegue Multi-AZ nativo en todas las capas (subredes en 2 zonas de disponibilidad).
   * Rolling Updates con health checks independientes en cada contenedor antes de drenar tareas antiguas.
4. **Optimización de Costos (COST 02 - Govern usage):**
   * Ahorro directo de **$32.40 USD/mes** al utilizar subredes públicas para las tareas de Fargate con Security Groups estrictos, eliminando la necesidad de un NAT Gateway innecesario en etapas iniciales.
   * Aprovisionamiento de `db.t3.micro` y tareas Fargate de 0.5 vCPU para operar el ERP completo por menos de **$40 USD/mes**.

---

## 🚀 Despliegue Rápido (Golden Path)

### 1. Inicializar el proyecto
```bash
terraform init
```

### 2. Configurar variables
Copiar el archivo de plantilla y ajustar valores:
```bash
cp terraform.tfvars.example terraform.tfvars
```

### 3. Previsualizar cambios
```bash
terraform plan
```

### 4. Aprovisionar infraestructura
```bash
terraform apply
```

### 5. Destruir entorno (al terminar pruebas)
```bash
terraform destroy
```
