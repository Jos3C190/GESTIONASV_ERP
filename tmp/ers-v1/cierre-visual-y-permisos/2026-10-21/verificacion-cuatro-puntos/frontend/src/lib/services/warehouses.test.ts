import { describe, expect, it } from 'vitest';
import { mapWarehouseOutToWarehouse } from './warehouses';
import type { WarehouseOut } from '$lib/api/client';

describe('mapWarehouseOutToWarehouse', () => {
  it('conserva descripción y galería entregadas por el backend', () => {
    const source = {
      id:'w1',company_id:'company-1',warehouse_category_id:'c1',code:'A-1',name:'Central',description:'Principal',
      is_central:true,
      type:'general',status:'active',location:'Nivel 1',branch_id:'b1',branch_name:'Matriz',branch_address:'',
      area:10,height:2,length:5,width:2,shelves_total:3,shelves_occupied:0,
      certified_max_weight_kg:1000,operational_max_weight_kg:900,
      certified_usable_volume_m3:100,operational_usable_volume_m3:90,
      capacity_profile:'general_mixed',capacity_enforcement_mode:'observe',capacity_status:'available',
      storage_eligible:true,usable_length_m:5,usable_width_m:2,usable_height_m:2,products:0,
      manager:'Sin responsable',manager_employee_id:null,manager_initials:'—',operators:0,shifts:[],total_skus:0,
      top_categories:[],low_stock_items:0,expiring_items:0,inventory_value:0,inventory_turnover:0,last_movement:'',
      inbound_this_month:0,outbound_this_month:0,daily_movements_avg:0,trend:[],recent_movements:[],top_products:[],
      cameras:0,access_control:'sin_control',has_alarm:false,fire_system:[],last_security_audit:'',temperature_range:'',
      humidity_range:'',cooling:'ventilacion_natural',has_ventilation:false,last_maintenance:'',next_maintenance:'',
      maintenance_notes:'',sanitary_permit:null,sanitary_permit_expiry:null,last_inspection:'',certifications:[],
      images:[{url:'https://res.cloudinary.com/demo/image/upload/a.webp',caption:'Portada',public_id:'a'}],
      created_at:'2026-01-01T00:00:00Z',updated_at:null
    } satisfies WarehouseOut;
    const result = mapWarehouseOutToWarehouse(source);
    expect(result.description).toBe('Principal');
    expect(result.isCentral).toBe(true);
    expect(result.images).toEqual(source.images);
    expect(result.operationalMaxWeightKg).toBe(900);
    expect(result.operationalUsableVolumeM3).toBe(90);
    expect(result.capacityStatus).toBe('available');
  });

  it('preserves a company-level warehouse without a branch', () => {
    const source = {
      id: 'w2',
      company_id: 'company-1',
      warehouse_category_id: 'c1',
      code: 'MATRIZ',
      name: 'Bodega matriz',
      description: null,
      is_central: true,
      type: 'general',
      status: 'active',
      location: '',
      branch_id: null,
      branch_name: 'Casa matriz · independiente',
      branch_address: '',
      area: 0,
      height: 0,
      length: 0,
      width: 0,
      shelves_total: 0,
      shelves_occupied: null,
      certified_max_weight_kg: null,
      operational_max_weight_kg: null,
      certified_usable_volume_m3: null,
      operational_usable_volume_m3: null,
      capacity_profile: 'general_mixed',
      capacity_enforcement_mode: 'disabled',
      capacity_status: 'not_configured',
      storage_eligible: true,
      usable_length_m: null,
      usable_width_m: null,
      usable_height_m: null,
      products: null,
      manager: 'Sin responsable',
      manager_employee_id: null,
      manager_initials: '—',
      operators: 0,
      shifts: [],
      total_skus: 0,
      top_categories: [],
      low_stock_items: 0,
      expiring_items: 0,
      inventory_value: 0,
      inventory_turnover: 0,
      last_movement: '',
      inbound_this_month: 0,
      outbound_this_month: 0,
      daily_movements_avg: 0,
      trend: [],
      recent_movements: [],
      top_products: [],
      cameras: 0,
      access_control: 'sin_control',
      has_alarm: false,
      fire_system: [],
      last_security_audit: '',
      temperature_range: '',
      humidity_range: '',
      cooling: 'sin_climatizacion',
      has_ventilation: false,
      last_maintenance: '',
      next_maintenance: '',
      maintenance_notes: '',
      sanitary_permit: null,
      sanitary_permit_expiry: null,
      last_inspection: '',
      certifications: [],
      images: [],
      created_at: '2026-01-01T00:00:00Z',
      updated_at: null
    } satisfies WarehouseOut;

    const result = mapWarehouseOutToWarehouse(source);

    expect(result.companyId).toBe('company-1');
    expect(result.branchId).toBeNull();
    expect(result.branchName).toBe('Casa matriz · independiente');
  });
});
