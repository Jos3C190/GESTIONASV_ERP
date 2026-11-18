import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const SCREENSHOT_DIR = path.resolve(process.cwd(), '../../reuniones-docs-erp/evidencias-qa');

test.beforeAll(async () => {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }
});

test.describe('Mega QA ERP — Recorrido Completo de Cómputo III', () => {

  test('1. Flujo Completo con Superadmin: Inventario, Kardex, Ventas y DTE', async ({ page }) => {
    // 1.1 Iniciar Sesión como superadmin
    await page.goto('/login');
    await expect(page).toHaveTitle(/Iniciar sesión/);
    
    await page.fill('#login', 'superadmin');
    await page.fill('#password', 'Admin2026Seguro!');
    await page.click('button[type="submit"]');

    // Navegar y seleccionar empresa
    await page.waitForURL(/\/(splash|companies|dashboard)/, { timeout: 15000 });
    await page.goto('/companies');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: `${SCREENSHOT_DIR}/01_seleccion_empresa_superadmin.png`, fullPage: true });

    // Seleccionar la primera empresa activa
    const companyCard = page.locator('article button').first();
    if (await companyCard.isVisible()) {
      await companyCard.click();
      await page.waitForTimeout(2000);
    }

    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: `${SCREENSHOT_DIR}/01b_dashboard_superadmin.png`, fullPage: true });

    // 1.2 Módulo de Inventario y Kardex
    await page.goto('/inventory');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: `${SCREENSHOT_DIR}/02_modulo_inventario_general.png`, fullPage: true });

    await page.goto('/inventory/kardex');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: `${SCREENSHOT_DIR}/03_kardex_inmutable.png`, fullPage: true });

    // 1.3 Módulo de Traslados y Logística
    await page.goto('/transfers');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: `${SCREENSHOT_DIR}/04_traslados_flota.png`, fullPage: true });

    // 1.4 Módulo Comercial y Ventas
    await page.goto('/customers');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: `${SCREENSHOT_DIR}/05_clientes_fiscales.png`, fullPage: true });

    await page.goto('/sales/quotations');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: `${SCREENSHOT_DIR}/06_cotizaciones_ventas.png`, fullPage: true });

    await page.goto('/sales');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: `${SCREENSHOT_DIR}/07_pedidos_ventas.png`, fullPage: true });

    // 1.5 Módulo de Facturación DTE y Contingencias
    await page.goto('/sales/fiscal-documents');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: `${SCREENSHOT_DIR}/08_documentos_dte.png`, fullPage: true });

    await page.goto('/sales/contingencies');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: `${SCREENSHOT_DIR}/09_contingencias_tributarias.png`, fullPage: true });
  });

  test('2. Verificación de Roles Operativos: Compras, Bodega y Flota', async ({ page }) => {
    // 2.1 Andrea Menjívar (Gerente de Compras)
    await page.goto('/login');
    await page.fill('#login', 'andrea.menjivar');
    await page.fill('#password', 'Lorena2026!');
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/(splash|companies|dashboard)/, { timeout: 15000 });
    await page.goto('/companies');
    await page.waitForLoadState('networkidle');
    const compAndrea = page.locator('article button').first();
    if (await compAndrea.isVisible()) {
      await compAndrea.click();
      await page.waitForTimeout(2000);
    }
    await page.goto('/purchases');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: `${SCREENSHOT_DIR}/10_rol_andrea_compras.png`, fullPage: true });

    // Cerrar sesión
    await page.evaluate(() => localStorage.clear());

    // 2.2 Ricardo Portillo (Bodeguero Central)
    await page.goto('/login');
    await page.fill('#login', 'ricardo.portillo');
    await page.fill('#password', 'Lorena2026!');
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/(splash|companies|dashboard)/, { timeout: 15000 });
    await page.goto('/companies');
    await page.waitForLoadState('networkidle');
    const compRicardo = page.locator('article button').first();
    if (await compRicardo.isVisible()) {
      await compRicardo.click();
      await page.waitForTimeout(2000);
    }
    await page.goto('/inventory');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: `${SCREENSHOT_DIR}/11_rol_ricardo_bodega.png`, fullPage: true });

    // Cerrar sesión
    await page.evaluate(() => localStorage.clear());

    // 2.3 Mauricio Hernández (Jefe de Flota)
    await page.goto('/login');
    await page.fill('#login', 'mauricio.hernandez');
    await page.fill('#password', 'Lorena2026!');
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/(splash|companies|dashboard)/, { timeout: 15000 });
    await page.goto('/companies');
    await page.waitForLoadState('networkidle');
    const compMauricio = page.locator('article button').first();
    if (await compMauricio.isVisible()) {
      await compMauricio.click();
      await page.waitForTimeout(2000);
    }
    await page.goto('/transfers');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: `${SCREENSHOT_DIR}/12_rol_mauricio_flota.png`, fullPage: true });
  });

});
