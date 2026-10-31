# Moneda de COM-00022 frente a valoración de la empresa

Fecha: 21/10/2026, America/El_Salvador. Diagnóstico de solo lectura.

## Datos comprobados

| Documento/configuración | Estado | Moneda |
| --- | --- | --- |
| Cotización COT-00047 | Origen de la orden | CRC |
| Orden OC-00022 | received | CRC |
| Recepción COM-00022 | received, sin movimiento de inventario | CRC |
| Valoración de Grupo Lorena | Activa desde 17/10/2026 UTC | USD |

La captura corresponde a otra recepción distinta de COM-00021. CRC es el código del colón costarricense. La compra conserva la moneda de su orden y cotización; no la eligió automáticamente el paso de verificación.

`inventory_valuation_repository.py` rechaza la recepción cuando `valuation_currency` difiere de la moneda activa de valoración, mediante `valuation_currency_mismatch`. Impide sumar un importe CRC al saldo USD sin una conversión. La corrección previa de presentaciones no modifica monedas ni resuelve esta diferencia.

## Evidencia y límite

Consulta y resultado: `tmp/ers-v1/2026-10-21-moneda-recepcion/diagnostico-solo-lectura.py`, `diagnostico.log` y `diagnostico.exit` (0). Se comprobó `transaction_read_only = on`; no se cambiaron documentos, monedas, importes, estados ni existencias.

## Confirmación del usuario y resolución

El usuario confirmó que quería probar la operación en colones. Se conserva CRC y se añadió la conversión documentada de la recepción a USD. Ver [implementación, evidencia y continuación manual](conversion-monedas-compras-2026-10-21.md). La tasa real o ficticia de su documento aún debe introducirla el usuario; el valor 500 utilizado en las pruebas no se guardó en COM-00022.
