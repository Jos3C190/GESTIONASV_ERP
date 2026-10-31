# Línea base — pasada final B01–B08

- Fecha: 20/10/2026, zona America/El_Salvador.
- Rama: codex/block-2-stabilization-2026-09-30.
- Árbol compartido: 490 rutas con cambios (modificadas y no rastreadas) antes de esta pasada; se preservan sin reset ni limpieza.
- Servicios Docker: frontend, backend, db, Redis, OCR, almacenamiento y observabilidad en ejecución.
- Base configurada por la API: erp_db; Alembic: 0090 (head). La base de demostración no se escribe durante la auditoría.
- Conteo inicial en transacción READ ONLY:
  - ERS-INC-EE8FE228: físico 4; valorado 4; USD 40; costo medio USD 10.
  - ERS-LATE-B1B55D6D: físico 5; valorado 5; USD 60; costo medio USD 12.
  - ERS-REVIEW-DD6BBF85: físico 12; valorado 12; USD 160; costo medio USD 13.333333.
  - ERS-UI-F767BABC: físico 0; valorado 0; USD 0; costo medio USD 0.
- La matriz anterior presenta evidencia de 23 E2E y otras 10 E2E. Revisaré logs recuperables y no sumaré repeticiones a esos conteos.
- Nota: el chequeo inicial de pikepdf/pytest se hizo en contenedores separados: backend dev tiene pytest pero no pikepdf; ocr-worker tiene pikepdf/ocrmypdf pero no pytest. No se instaló nada en ninguno.
