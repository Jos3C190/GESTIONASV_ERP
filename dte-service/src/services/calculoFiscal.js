/**
 * Cálculo fiscal compartido entre Factura, CCF, Nota de Crédito/Débito y
 * Comprobante de Liquidación.
 *
 * Reglas oficiales (Manual Funcional v2.0, secciones XVIII y XXI):
 *  - Por línea: venta = cantidad × precioUni − montoDescu, con holgura ±0.01.
 *  - descuNoSuj / descuExenta / descuGravada del resumen son descuentos
 *    GLOBALES y subTotal = subTotalVentas − descuentos globales.
 *  - totalDescu es informativo: descuentos por ítem + descuentos globales.
 *  - Campos del cuerpo admiten 8 decimales; los del resumen 2 (half-up).
 *
 * Este servicio representa todo descuento global prorrateándolo a las líneas
 * (`aplicarDescuentoGlobal`). Así cada línea sigue cumpliendo la fórmula, los
 * campos de descuento global del resumen quedan en 0 y totalDescu es la suma
 * de montoDescu.
 */
const HOLGURA = 0.01;
const TOLERANCIA_FLOTANTE = 1e-9;

/** Redondeo half-up a `decimales` evitando el error binario de toFixed (1.005 → 1.01). */
function redondear(valor, decimales = 2) {
  if (!Number.isFinite(valor)) throw new Error('Monto no numérico');
  const signo = valor < 0 ? -1 : 1;
  const texto = Math.abs(valor).toFixed(12);
  return signo * Number(`${Math.round(Number(`${texto}e${decimales}`))}e-${decimales}`);
}

const r2 = (valor) => redondear(valor, 2);
const r8 = (valor) => redondear(valor, 8);

function errorDeSolicitud(mensaje) {
  return Object.assign(new Error(mensaje), { code: 'INVALID_DTE_REQUEST' });
}

/**
 * Totales del resumen a partir de líneas ya construidas. Los descuentos
 * globales son 0 porque siempre se prorratean a las líneas.
 */
function calcularVentasPorCategoria(items) {
  let totalGravada = 0;
  let totalExenta = 0;
  let totalNoSuj = 0;
  let totalDescu = 0;
  let totalNoGravado = 0;

  for (const item of items) {
    totalGravada += item.ventaGravada ?? 0;
    totalExenta += item.ventaExenta ?? 0;
    totalNoSuj += item.ventaNoSuj ?? 0;
    totalDescu += item.montoDescu ?? 0;
    totalNoGravado += item.noGravado ?? 0;
  }

  return {
    totalGravada: r2(totalGravada),
    totalExenta: r2(totalExenta),
    totalNoSuj: r2(totalNoSuj),
    descuGravada: 0,
    descuExenta: 0,
    descuNoSuj: 0,
    totalDescu: r2(totalDescu),
    totalNoGravado: r2(totalNoGravado),
  };
}

/**
 * Valida cada línea antes de reservar el número de control: montos no
 * negativos y cantidad × precioUni − montoDescu = venta dentro de la holgura.
 * Los cargos/abonos que no afectan la base (`noGravado`) exigen al menos una
 * venta mayor a cero en el documento (Manual Funcional XII).
 */
function validarLineas(items) {
  let hayVenta = false;
  let hayNoGravado = false;

  items.forEach((item, indice) => {
    const linea = indice + 1;
    if (typeof item?.descripcion !== 'string' || !item.descripcion.trim()) {
      throw errorDeSolicitud(`Línea ${linea}: la descripción es obligatoria`);
    }
    if (typeof item.cantidad !== 'number' || !Number.isFinite(item.cantidad) || item.cantidad <= 0) {
      throw errorDeSolicitud(`Línea ${linea}: la cantidad debe ser mayor a cero`);
    }
    if (typeof item.precioUni !== 'number' || !Number.isFinite(item.precioUni) || item.precioUni < 0) {
      throw errorDeSolicitud(`Línea ${linea}: precioUni debe ser un número no negativo`);
    }
    for (const campo of ['montoDescu', 'ventaGravada', 'ventaExenta', 'ventaNoSuj']) {
      const valor = item[campo] ?? 0;
      if (typeof valor !== 'number' || !Number.isFinite(valor) || valor < 0) {
        throw errorDeSolicitud(`Línea ${linea}: ${campo} debe ser un número no negativo`);
      }
    }
    const noGravado = item.noGravado ?? 0;
    if (typeof noGravado !== 'number' || !Number.isFinite(noGravado)) {
      throw errorDeSolicitud(`Línea ${linea}: noGravado debe ser numérico`);
    }

    const ventas = (item.ventaGravada ?? 0) + (item.ventaExenta ?? 0) + (item.ventaNoSuj ?? 0);
    const esperado = item.cantidad * item.precioUni - (item.montoDescu ?? 0);
    if (Math.abs(esperado - ventas) > HOLGURA + TOLERANCIA_FLOTANTE) {
      throw errorDeSolicitud(
        `Línea ${linea}: cantidad × precioUni − montoDescu (${esperado.toFixed(2)}) no coincide con la venta informada (${ventas.toFixed(2)})`,
      );
    }
    if (ventas > 0) hayVenta = true;
    if (noGravado !== 0) hayNoGravado = true;
  });

  if (hayNoGravado && !hayVenta) {
    throw errorDeSolicitud('Los cargos/abonos que no afectan la base imponible requieren al menos una venta mayor a cero');
  }
}

/**
 * Porcentaje informativo de descuento sobre la base antes de descuentos.
 * Se conserva para compatibilidad; Factura y CCF informan 0 porque no
 * transmiten descuentos globales.
 */
function calcularPorcentajeDescuento(subTotalVentasNeto, totalDescu) {
  const baseAntesDeDescuento = subTotalVentasNeto + totalDescu;
  if (baseAntesDeDescuento <= 0) return 0;
  return r2((totalDescu / baseAntesDeDescuento) * 100);
}

/** Reparte centavos por el método del mayor residuo; la suma es exacta. */
function prorratearCentavos(totalCentavos, pesos) {
  const pesoTotal = pesos.reduce((suma, peso) => suma + Math.max(0, peso), 0);
  if (totalCentavos <= 0 || pesoTotal <= 0) return pesos.map(() => 0);
  const exactos = pesos.map((peso) => (totalCentavos * Math.max(0, peso)) / pesoTotal);
  const asignados = exactos.map(Math.floor);
  let resto = totalCentavos - asignados.reduce((suma, valor) => suma + valor, 0);
  const orden = exactos
    .map((valor, indice) => ({ indice, fraccion: valor - asignados[indice] }))
    .sort((a, b) => b.fraccion - a.fraccion || a.indice - b.indice);
  for (let i = 0; resto > 0; i += 1, resto -= 1) asignados[orden[i % orden.length].indice] += 1;
  return asignados;
}

/**
 * Prorratea un descuento GLOBAL ({ gravada?, exenta?, noSuj? } en dólares)
 * entre las líneas de cada categoría, en centavos exactos. Cada línea
 * conserva su precio, aumenta su montoDescu y reduce su venta, de modo que
 * sigue cumpliendo cantidad × precioUni − montoDescu = venta.
 *
 * Devuelve un arreglo nuevo; no muta el original.
 */
function aplicarDescuentoGlobal(items, descuentoGlobal) {
  if (!descuentoGlobal) return items;

  const nuevos = items.map((item) => ({ ...item }));
  const categorias = [
    ['ventaGravada', descuentoGlobal.gravada ?? 0],
    ['ventaExenta', descuentoGlobal.exenta ?? 0],
    ['ventaNoSuj', descuentoGlobal.noSuj ?? 0],
  ];

  for (const [campo, monto] of categorias) {
    if (typeof monto !== 'number' || !Number.isFinite(monto) || monto < 0) {
      throw errorDeSolicitud(`El descuento global de ${campo} debe ser un número no negativo`);
    }
    if (monto === 0) continue;
    const pesos = items.map((item) => Math.round((item[campo] ?? 0) * 100));
    const totalCategoria = pesos.reduce((suma, peso) => suma + peso, 0);
    const centavos = Math.round(monto * 100);
    if (centavos > totalCategoria) {
      throw errorDeSolicitud(`El descuento global de ${campo} excede el total de esa categoría`);
    }
    prorratearCentavos(centavos, pesos).forEach((descuentoCentavos, indice) => {
      if (descuentoCentavos === 0) return;
      const descuento = descuentoCentavos / 100;
      nuevos[indice][campo] = r2((nuevos[indice][campo] ?? 0) - descuento);
      nuevos[indice].montoDescu = r2((nuevos[indice].montoDescu ?? 0) + descuento);
    });
    // El IVA por línea informado por el cliente ya no corresponde a la nueva
    // base gravada; se descarta en todas las líneas para recalcularlo.
    if (campo === 'ventaGravada') nuevos.forEach((item) => delete item.ivaItem);
  }
  return nuevos;
}

module.exports = {
  HOLGURA,
  redondear,
  r2,
  r8,
  calcularVentasPorCategoria,
  validarLineas,
  calcularPorcentajeDescuento,
  aplicarDescuentoGlobal,
  prorratearCentavos,
};
