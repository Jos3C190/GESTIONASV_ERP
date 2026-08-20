# Capacidad fisica e inventario por ubicacion

## Principios

La capacidad fisica se controla en unidades canonicas de peso (`kg`) y volumen
util (`m3`). El sistema no presupone pallets ni convierte el area o las
dimensiones exteriores de un edificio en volumen util. Los limites deben ser
aprobados por la operacion, el fabricante de la estructura o el responsable de
seguridad correspondiente.

Cada alcance administrado (almacen, grupo estructural o ubicacion) puede tener
dos limites por metrica:

- **Certificado:** limite fisico o regulatorio que nunca puede excederse.
- **Operativo:** limite diario, igual o inferior al certificado. Solo este
  limite admite una excepcion temporal, autorizada y auditada.

En la primera version, la excepcion se concede a una ubicacion concreta. Los
limites operativos compartidos del grupo estructural y del almacen permanecen
vigentes; una autorizacion local nunca relaja esos alcances ni el limite
certificado.

La suma de los maximos de ubicaciones no se interpreta como la resistencia del
almacen. La ocupacion real y comprometida se valida en la ubicacion y en cada
grupo estructural antecesor.

## Jerarquia de configuracion

La ruta aplicable es `ubicacion -> estructuras antecesoras -> almacen`. Una
ubicacion puede depender de una estructura compartida (rack, bahia, nivel,
camara o zona) o directamente del almacen. En ambos casos, la ubicacion sigue
siendo el destino que guarda la unidad logistica; la estructura solo aporta un
limite compartido.

Los limites se comparan como pares equivalentes e independientes:

- ubicacion asociada contra su estructura inmediata;
- ubicacion independiente contra el almacen;
- estructura hija contra su estructura padre;
- estructura raiz contra el almacen;
- peso contra peso y volumen contra volumen;
- certificado contra certificado y operativo contra operativo.

Si ambos limites existen, el hijo no puede superar al padre, incluso en modo
`observe` o `disabled`. Si al padre le falta esa metrica, la configuracion se
permite y el diagnostico reporta `parent_limit_not_configured`. La suma de los
maximos nominales de hijos es solo un dato de planeacion: cuando supera el
limite del padre se reporta `nominal_capacity_overallocated`, pero no se
interpreta como ocupacion ni bloquea por si sola.

Al crear un limite antes inexistente, reducirlo o activar `enforce`, el sistema
comprueba `ocupado + reservas vigentes`. Rechaza el cambio si el consumo supera
el nuevo limite o si existen mediciones incompletas que impiden demostrar que
la reduccion es segura. Una excepcion operativa no autoriza una reduccion. Al
mover una ubicacion o reubicar una estructura se valida el consumo combinado en
cada nuevo antecesor bajo el bloqueo transaccional del almacen.

Las estructuras con subestructuras activas o ubicaciones activas asignadas no
pueden desactivarse. Las dimensiones de encaje de mercancia continuan siendo
una politica de la ubicacion y no se suman ni comparan entre nodos.

## Consulta de ubicaciones por estructura

La pantalla de estructuras ofrece `Ver ubicaciones` para abrir directamente la
lista del almacén con el filtro de esa estructura. Al seleccionar una
estructura se incluyen sus ubicaciones directas y las de todas sus
subestructuras, porque el límite compartido se aplica a todo ese subarbol.
La lista conserva la ruta completa y distingue entre:

- **Directa del almacén:** `capacity_group_id` es nulo; la ubicación no depende
  de una estructura compartida.
- **Estructura y subestructuras:** consulta una estructura y todos sus niveles
  descendientes.

El filtro de estructura es una consulta de asignación física: sus conteos no
representan inventario ocupado, reservas ni capacidad disponible. También se
pueden consultar las ubicaciones sin estructura y combinar cualquiera de estos
criterios con búsqueda, área, tipo y estado.

Las operaciones extensas de ubicación se realizan en páginas dedicadas para mantener el listado
limpio: `Nueva ubicación`, `Editar ubicación`, `Generar ubicaciones por rangos` e `Importar
ubicaciones`. Los formularios conservan las mismas validaciones, permisos y confirmaciones que
los flujos anteriores; solo cambia su presentación de modal a página.

## Metricas

Para peso y volumen se calculan de forma independiente:

```text
ocupado = inventario fisicamente confirmado
reservado = putaway o traslado entrante pendiente de confirmacion
proyectado = ocupado + reservado
disponible_operativo = limite_operativo - proyectado
utilizacion = proyectado / limite_operativo
```

El indicador resumido es el mayor porcentaje entre peso y volumen, pero la API
y la interfaz siempre muestran ambas metricas y la restriccion dominante. Un
valor desconocido nunca se convierte en cero.

Estados derivados iniciales:

- `not_configured`: faltan limites requeridos.
- `incomplete`: existe inventario sin medidas confiables.
- `available`: utilizacion menor a 80 %.
- `warning`: utilizacion desde 80 % y menor a 90 %.
- `critical`: utilizacion desde 90 % y menor a 100 %.
- `full`: utilizacion proyectada igual o superior al limite operativo.
- `over_operational`: existe una excepcion temporal vigente por encima del
  limite operativo y sin superar el certificado.
- `over_certified`: peligro de seguridad; la carga proyectada conocida supera
  un limite certificado. Tiene prioridad sobre `over_operational` y `full`, y
  ninguna excepcion operativa puede ocultarlo o autorizarlo.

Estos estados no reemplazan el estado operativo (`active`, `maintenance` o
`inactive`).

## Presentaciones y unidades logisticas

Un producto independiente o una variante inventariable tiene una unidad base.
Sus presentaciones (pieza, caja, saco, paquete, rollo, tambor, contenedor o
producto suelto) declaran cantidad base contenida, peso bruto, dimensiones
exteriores, volumen, apilabilidad y version.

Una unidad logistica ligera representa un bulto o conjunto homogeneo y conserva
un snapshot de sus medidas. Las mediciones reales de recepcion prevalecen sobre
la presentacion maestra. No se modelan contenedores anidados. La primera version
mueve o despacha una unidad logistica completa; dividir, unir y reempacar quedan
como operaciones explicitas posteriores para no alterar trazabilidad mediante
ediciones silenciosas.

## Reglas de los flujos

- Una recepcion prevista no ocupa capacidad.
- La asignacion planificada de un putaway o traslado debe reservar la capacidad
  del destino antes de confirmarse.
- Confirmar el movimiento convierte la reserva en ocupacion real.
- Un picking abierto no libera capacidad; la confirmacion fisica si.
- Cancelar o vencer una tarea libera su reserva.
- Un traslado libera origen y ocupa destino en una unica transaccion.
- Inventario en cuarentena, bloqueado o danado continua ocupando espacio.
- Mercaderia sin peso o volumen confiable solo puede recibirse en cuarentena.
- Para salir de cuarentena debe contar con medidas verificadas.
- El putaway valida peso, volumen, dimensiones, elegibilidad y todos los grupos
  estructurales aplicables. El perfil `cold` deja el punto de extensión para la
  política térmica; no interpreta rangos de temperatura escritos como texto.
- Un limite certificado no admite excepciones.

## Perfiles

En esta version los perfiles clasifican la operacion y permiten ampliar sus
reglas sin reinterpretar datos libres. El motor comun ya valida kg, m3,
dimensiones configuradas y grupos estructurales. Los controles especializados
indicados como pendientes siguen siendo procedimientos operativos, no reglas
calculadas por el sistema.

- `general_mixed`: peso y volumen para bodegas mixtas.
- `rack`: identifica ubicaciones que usan dimensiones y grupos compartidos de
  rack, bahia o nivel.
- `bulk_floor`: identifica almacenamiento sobre piso. La presion por area y la
  estabilidad de apilamiento requieren un motor especializado posterior.
- `cold`: identifica cámaras y usa volumen útil aprobado para circulación; el
  motor estructurado de compatibilidad térmica se activa por separado.
- `oversize_manual`: identifica bultos que requieren revision dimensional y
  autorizacion del procedimiento del almacen.
- `transit`: identifica espacio temporal; puede configurarse como no elegible
  para almacenamiento normal y sin control nominal.

Materiales peligrosos requieren reglas de compatibilidad y limites regulatorios
que no se deducen de peso o volumen. Hasta que ese motor exista, su ubicacion
debe permanecer manual y controlada.

## Limites explicitos de la primera version

- No hay contenedores anidados ni division, union o reempaque automaticos de HU.
- El ledger publicado es inmutable, pero el comando dedicado de reversion
  compensatoria aun debe incorporarse antes de operar correcciones desde la UI.
- Las excepciones operativas se limitan a ubicaciones; no relajan grupos ni el
  almacen completo.
- Presion por area, estabilidad de apilado, compatibilidad termica, segregacion
  de materiales peligrosos y permanencia de cross-dock esperan motores de reglas
  propios. No se simulan con texto ni se deducen de kg/m3.

## Casos operativos de referencia

| Operacion real | Configuracion minima | Regla dominante habitual |
| --- | --- | --- |
| Cuarto de repuestos pequeno | Perfil mixto, kg y m3 por ubicacion | Volumen para cajas livianas; peso para piezas metalicas |
| Trastienda de comercio | Mixto, zonas de estante y piso | Volumen util y dimensiones; pasillos no cuentan como almacenaje |
| Sacos o granel sobre piso | `bulk_floor`, grupo de piso, kg y m3 | Peso y volumen; carga por area y estabilidad se controlan por procedimiento hasta incorporar su motor |
| Rack selectivo mediano | `rack`, grupos rack/bahia/nivel | Menor limite entre nivel, bahia, rack y ubicacion |
| Centro de distribucion mixto | Presentaciones versionadas y reservas de putaway | Metrica limitante por cada destino, no un promedio global |
| Camara fria | `cold`, kg, volumen util y rango termico operativo externo | El sistema controla kg/m3; compatibilidad termica espera su motor dedicado |
| Cross-dock o staging | `transit`, no elegible para almacenamiento normal | El sistema no inventa capacidad; permanencia y congestion esperan reglas dedicadas |
| Producto sobredimensionado | `oversize_manual`, dimensiones reales | Encaje geometrico cuando hay dimensiones configuradas y revision operativa |

Ejemplo: una ubicacion con limite operativo de `1 000 kg` y `8 m3` contiene
`600 kg / 6 m3` y tiene reservado un ingreso de `100 kg / 1.5 m3`. La carga
proyectada es `700 kg / 7.5 m3`: peso `70 %`, volumen `93.75 %`. El estado es
`critical` y la metrica limitante es volumen. No se promedian ambos porcentajes.

Una caja, saco, rollo o producto suelto no cambia esta formula. La forma fisica
se conserva en la presentacion o medicion real; el sistema calcula su peso y volumen total y,
cuando el perfil lo exige, valida tambien que las dimensiones quepan. De este modo
la operacion no depende de conocer de antemano un tipo unico de contenedor.

## Controles diarios

- Recepcion verifica unidad, cantidad base, lote/vencimiento cuando aplique y
  peso/medidas de una muestra representativa o del bulto real.
- Putaway reserva antes de asignar el destino y vuelve a validar al confirmar.
- Conteos fisicos reconcilian saldos, unidades logisticas y ubicacion real.
- Reservas vencidas y excepciones operativas proximas a vencer se revisan por
  turno; no se renuevan automaticamente.
- Cambiar un limite certificado requiere una nueva fuente de aprobacion; no se
  trata como un ajuste rutinario del sistema.
- Los tableros separan datos desconocidos, incompletos y cero real.

## Activacion

La aplicacion por almacen o perfil progresa por `disabled`, `observe` y
`enforce`. Para activar `enforce` se requiere:

1. Limites aprobados en todas las ubicaciones normales.
2. Grupos estructurales configurados donde correspondan.
3. Ninguna unidad sin medir fuera de cuarentena.
4. Saldos reconciliados contra un conteo fisico.
5. Un periodo de observacion sin discrepancias no explicadas.
6. Aprobacion del responsable del almacen.

## Matriz minima de aceptacion

| Escenario | Resultado esperado |
| --- | --- |
| Diez cajas de 12 unidades | Se convierten 120 unidades base y se consume diez veces el peso/volumen por caja |
| Caja liviana pero voluminosa | Se admite por peso y se rechaza o alerta por volumen |
| Pieza pequena y muy pesada | Se admite por volumen y se rechaza o alerta por peso |
| Saco sin una medida confiable | Solo entra en cuarentena; el tablero marca ocupacion incompleta, no `0 %` |
| Dos operadores reservan el ultimo espacio | El bloqueo y la revalidacion permiten solo la combinacion que cabe |
| Reserva vencida | Deja de consumir proyeccion y queda con estado terminal auditable |
| Traslado entre almacenes | Origen y destino cambian juntos; un error revierte ambos |
| Picking creado pero no confirmado | La capacidad del origen no se libera |
| Exceso operativo autorizado | Requiere permiso, motivo y vencimiento; nunca supera el certificado |
| Exceso certificado con autorizacion operativa | Se rechaza siempre; si el exceso ya existe, el resumen muestra `over_certified` hasta corregirlo |
| Dos ubicaciones comparten un nivel de rack | Se validan ubicacion, nivel, antecesores y almacen |
| Maximos nominales de hijos mayores al padre | Se advierte sobreasignacion nominal; no se declara ocupacion ni se bloquea |
| Reduccion por debajo de ocupado + reservado | Se rechaza aun con una excepcion operativa vigente |
| Cambio jerarquico con unidades sin medir | Se rechaza si el destino tiene limites aplicables y no puede demostrarse seguridad |
| Zona de recepcion activa | Puede operar con perfil de transito sin inventar una capacidad nominal |
| Version nueva de una caja | Movimientos anteriores conservan el snapshot de la version usada |
| Lote vencido disponible | Se rechaza o se dirige a cuarentena |
| Reintento con la misma idempotencia | Devuelve el mismo movimiento; contenido distinto genera conflicto |
| Referencias de otra empresa | Se rechazan sin revelar si el recurso externo existe |
