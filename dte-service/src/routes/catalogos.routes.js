const express = require('express');
const { catalogosRaw, distritosDeDepartamento } = require('../config/catalogs');

const router = express.Router();

/** Lista todos los catálogos disponibles (id + título + cantidad de entradas). */
router.get('/', (req, res) => {
  const lista = Object.entries(catalogosRaw).map(([id, cat]) => ({
    id,
    titulo: cat.titulo,
    cantidadEntradas: cat.entradas.length,
  }));
  res.json(lista);
});

/**
 * Devuelve todas las entradas de un catálogo, con búsqueda opcional por texto.
 * GET /api/catalogos/CAT-019?q=programacion
 */
router.get('/:catId', (req, res) => {
  const cat = catalogosRaw[req.params.catId.toUpperCase()];
  if (!cat) return res.status(404).json({ error: `Catálogo ${req.params.catId} no encontrado` });

  const { q } = req.query;
  let entradas = cat.entradas.filter((e) => e.codigo !== '');
  if (q) {
    const needle = q
      .toString()
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, ''); // ignora acentos en la búsqueda
    entradas = entradas.filter((e) =>
      e.codigo.toLowerCase().includes(needle) || e.valor
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .includes(needle)
    );
  }

  res.json({ id: req.params.catId.toUpperCase(), titulo: cat.titulo, entradas });
});

/**
 * CAT-008 Distrito está agrupado por departamento (los códigos se repiten
 * entre departamentos). Este endpoint devuelve solo los distritos válidos
 * para un departamento específico (CAT-012).
 * GET /api/catalogos/CAT-008/departamento/06
 */
router.get('/CAT-008/departamento/:codDepartamento', (req, res) => {
  const distritos = distritosDeDepartamento(req.params.codDepartamento);
  if (!distritos.length) {
    return res.status(404).json({ error: `No hay distritos para el departamento ${req.params.codDepartamento}` });
  }
  res.json({ codDepartamento: req.params.codDepartamento, distritos });
});

module.exports = router;
