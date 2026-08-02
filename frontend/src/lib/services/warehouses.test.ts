import { describe, expect, it } from 'vitest';
import { mapWarehouseOutToWarehouse } from './warehouses';
import type { WarehouseOut } from '$lib/api/client';

describe('mapWarehouseOutToWarehouse', () => {
  it('conserva descripción y galería entregadas por el backend', () => {
    const source = {
      id:'w1',warehouse_category_id:'c1',code:'A-1',name:'Central',description:'Principal',
      type:'general',status:'active',location:'Nivel 1',branch_id:'b1',branch_name:'Matriz',branch_address:'',
      area:10,height:2,length:5,width:2,shelves_total:3,shelves_occupied:0,capacity:100,used:0,products:0,
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
    expect(result.images).toEqual(source.images);
  });
});
