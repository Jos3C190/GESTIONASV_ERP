#!/usr/bin/env node
/**
 * Genera una API key criptográficamente segura para autenticar consumidores
 * de este microservicio (tu ERP/POS), y la imprime lista para pegar en tu .env.
 *
 * Uso: node scripts/generar-api-key.js
 */
const crypto = require('crypto');

const key = crypto.randomBytes(32).toString('base64url');

console.log('Nueva API key generada:\n');
console.log(key);
console.log('\nAgrégala a tu .env así (si ya tienes otras, sepáralas con coma):');
console.log(`MS_API_KEYS=${key}`);
console.log('\nEl consumidor debe enviarla en cada request como uno de estos headers:');
console.log('  Authorization: Bearer ' + key);
console.log('  X-API-Key: ' + key);
