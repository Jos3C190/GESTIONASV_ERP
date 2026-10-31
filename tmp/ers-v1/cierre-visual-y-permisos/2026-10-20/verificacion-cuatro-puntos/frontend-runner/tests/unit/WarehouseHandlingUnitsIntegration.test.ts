import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import WarehouseDetailPage from '../../src/routes/(app)/warehouses/[id]/+page.svelte';

const mocks = vi.hoisted(() => ({
  getWarehouse: vi.fn(),
  getWarehouses: vi.fn(),
  listWarehouseMovements: vi.fn(),
  listHandlingUnits: vi.fn(),
  listReceiptLots: vi.fn(),
  listLocations: vi.fn(),
  prepareHandlingUnitSplit: vi.fn(),
  permissions: new Set<string>()
}));

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$app/state', () => ({
  page: {
    params: { id: 'warehouse-branch' },
    url: new URL('http://localhost/warehouses/warehouse-branch?tab=inventario')
  }
}));
vi.mock('$lib/services/warehouses', () => ({
  getWarehouse: mocks.getWarehouse,
  getWarehouses: mocks.getWarehouses
}));
vi.mock('$lib/features/inventory/services', () => ({
  inventoryApi: {
    listWarehouseMovements: mocks.listWarehouseMovements,
    listHandlingUnits: mocks.listHandlingUnits,
    listReceiptLots: mocks.listReceiptLots,
    confirmPutawayGroup: vi.fn(),
    verifyHandlingUnitMeasurements: vi.fn(),
    releaseHandlingUnit: vi.fn(),
    transferHandlingUnit: vi.fn(),
    prepareHandlingUnitSplit: mocks.prepareHandlingUnitSplit,
    createTraceCapability: vi.fn(),
    revokeTraceCapabilities: vi.fn(),
    previewInventoryLabel: vi.fn(),
    recordInventoryLabelPrint: vi.fn(),
    confirmInventoryLabelPlacement: vi.fn()
  }
}));
vi.mock('$lib/features/locations/services', () => ({
  listLocations: mocks.listLocations
}));
vi.mock('$lib/stores/company.svelte', () => ({ company: { id: 'company-test' } }));
vi.mock('$lib/stores/branch.svelte', () => ({ branch: { id: 'branch-test' } }));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    permissions: [],
    isSuperuser: false,
    hasPermission: (permission: string) => mocks.permissions.has(permission)
  }
}));
vi.mock('jsbarcode', () => ({ default: vi.fn() }));

function branchWarehouse(overrides: Record<string, unknown> = {}) {
  return {
    id: 'warehouse-branch',
    companyId: 'company-test',
    code: 'BOD-SM-01',
    name: 'Bodega de sucursal San Miguel',
    description: '',
    isCentral: false,
    type: 'general',
    status: 'active',
    location: 'Área posterior de la sucursal',
    branchId: 'branch-test',
    branchName: 'San Miguel',
    branchAddress: 'San Miguel',
    area: 20,
    height: 4,
    length: 5,
    width: 4,
    shelvesTotal: 0,
    shelvesOccupied: null,
    certifiedMaxWeightKg: 2000,
    operationalMaxWeightKg: 1500,
    certifiedUsableVolumeM3: 80,
    operationalUsableVolumeM3: 60,
    capacityProfile: 'general_mixed',
    capacityEnforcementMode: 'disabled',
    capacityStatus: 'available',
    storageEligible: true,
    usableLengthM: 5,
    usableWidthM: 4,
    usableHeightM: 4,
    products: 1,
    manager: 'Encargado de prueba',
    managerInitials: 'EP',
    operators: 1,
    shifts: ['mañana'],
    totalSKUs: 1,
    topCategories: [],
    lowStockItems: 0,
    expiringItems: 0,
    inventoryValue: 0,
    inventoryTurnover: 0,
    lastMovement: '',
    inboundThisMonth: 0,
    outboundThisMonth: 0,
    dailyMovementsAvg: 0,
    recentMovements: [],
    topProducts: [],
    cameras: 0,
    accessControl: 'sin_control',
    hasAlarm: false,
    fireSystem: [],
    lastSecurityAudit: '',
    temperatureRange: '',
    humidityRange: '',
    cooling: 'sin_climatizacion',
    hasVentilation: false,
    lastMaintenance: '',
    nextMaintenance: '',
    maintenanceNotes: '',
    sanitaryPermit: null,
    sanitaryPermitExpiry: null,
    lastInspection: '',
    certifications: [],
    images: [],
    createdAt: '2026-10-01T00:00:00Z',
    updatedAt: null,
    ...overrides
  };
}

function availableUnit() {
  return {
    id: 'hu-branch-1',
    company_id: 'company-test',
    warehouse_id: 'warehouse-branch',
    location_id: 'location-branch-1',
    inventory_item_id: 'item-1',
    packaging_definition_id: null,
    code: 'HU-BRANCH-001',
    lot_code: 'LOT-001',
    expiry_date: null,
    quantity_base: 10,
    actual_gross_weight_kg: 12,
    actual_length_m: null,
    actual_width_m: null,
    actual_height_m: null,
    actual_volume_m3: 1,
    occupied_weight_kg: 12,
    occupied_volume_m3: 1,
    stock_status: 'available',
    measurement_status: 'verified',
    measurement_source: 'manual',
    closed_at: null,
    release_requirements: [],
    created_at: '2026-10-10T12:00:00Z',
    updated_at: null
  };
}

describe('warehouse detail → HandlingUnitsPanel permissions', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mocks.permissions.clear();
    mocks.getWarehouse.mockResolvedValue(branchWarehouse());
    mocks.getWarehouses.mockResolvedValue({
      items: [],
      meta: { page: 1, size: 100, total: 0, pages: 0 }
    });
    mocks.listWarehouseMovements.mockResolvedValue([]);
    mocks.listHandlingUnits.mockResolvedValue([availableUnit()]);
    mocks.listReceiptLots.mockResolvedValue({
      items: [],
      meta: { page: 1, size: 20, total: 0, pages: 0 }
    });
    mocks.listLocations.mockResolvedValue({
      items: [
        {
          id: 'location-branch-1',
          code: 'SM-R01-N01-P01',
          is_active: true,
          storage_eligible: true,
          lifecycle_status: 'active'
        }
      ],
      meta: { page: 1, size: 100, total: 1, pages: 1 }
    });
  });

  it('permite preparar fracciones en sucursal y conserva el despacho completo en matriz', async () => {
    mocks.permissions.add('inventory:read');
    mocks.permissions.add('inventory:move');
    render(WarehouseDetailPage);

    expect(await screen.findByText('HU-BRANCH-001')).toBeInTheDocument();
    await fireEvent.click(screen.getByText('Otras acciones'));
    expect(await screen.findByRole('button', { name: 'Dividir unidad' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Trasladar a sucursal' })).not.toBeInTheDocument();
    await waitFor(() =>
      expect(mocks.listHandlingUnits).toHaveBeenCalledWith('warehouse-branch', {
        includeClosed: false
      })
    );
  });

  it('no permite preparar desde una bodega de sucursal no apta', async () => {
    mocks.permissions.add('inventory:read');
    mocks.permissions.add('inventory:move');
    mocks.getWarehouse.mockResolvedValue(branchWarehouse({ storageEligible: false }));
    render(WarehouseDetailPage);

    expect(await screen.findByText('HU-BRANCH-001')).toBeInTheDocument();
    const actions = screen.queryByText('Otras acciones');
    if (actions) await fireEvent.click(actions);
    expect(screen.queryByRole('button', { name: 'Dividir unidad' })).not.toBeInTheDocument();
    expect(mocks.prepareHandlingUnitSplit).not.toHaveBeenCalled();
  });

  it('no permite preparar sin inventory:move aunque la bodega esté apta', async () => {
    mocks.permissions.add('inventory:read');
    render(WarehouseDetailPage);

    expect(await screen.findByText('HU-BRANCH-001')).toBeInTheDocument();
    const actions = screen.queryByText('Otras acciones');
    if (actions) await fireEvent.click(actions);
    expect(screen.queryByRole('button', { name: 'Dividir unidad' })).not.toBeInTheDocument();
    expect(mocks.prepareHandlingUnitSplit).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'Trasladar a sucursal' })).not.toBeInTheDocument();
  });
});
