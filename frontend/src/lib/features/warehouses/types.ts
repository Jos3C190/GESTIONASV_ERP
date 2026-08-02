export type WarehouseStatus = 'active' | 'full' | 'maintenance' | 'inactive';
export type WarehouseType = 'general' | 'cold_storage' | 'hazmat' | 'transit' | 'bonded' | 'automated';
export type AccessControlType = 'biometrico' | 'tarjetas' | 'teclado' | 'doble_llave' | 'sin_control';
export type CoolingType = 'industrial_ac' | 'refrigeracion' | 'ventilacion_natural' | 'mixto' | 'sin_climatizacion';
export interface WarehouseImage { url: string; caption: string; public_id?: string; }
export interface WarehouseProduct { sku:string; name:string; category:string; quantity:number; unit:string; minStock:number; maxStock:number; expiryDate:string|null; }
export interface WarehouseMovement { id:string; date:string; type:'inbound'|'outbound'|'transfer'|'adjustment'; productSku:string; productName:string; quantity:number; operator:string; reference:string; }
export interface Warehouse {
  id:string; categoryId?:string; code:string; name:string; description:string; type:WarehouseType;
  status:WarehouseStatus; location:string; branchId:string; branchName:string; branchAddress:string;
  area:number; height:number; length:number; width:number; shelvesTotal:number; shelvesOccupied:number;
  capacity:number; used:number; products:number; manager:string; managerEmployeeId?:string|null;
  managerInitials:string; operators:number; shifts:('mañana'|'tarde'|'noche')[];
  totalSKUs:number; topCategories:string[]; lowStockItems:number; expiringItems:number;
  inventoryValue:number; inventoryTurnover:number; lastMovement:string; inboundThisMonth:number;
  outboundThisMonth:number; dailyMovementsAvg:number; trend?:number[]; recentMovements:WarehouseMovement[];
  topProducts:WarehouseProduct[]; cameras:number; accessControl:AccessControlType; hasAlarm:boolean;
  fireSystem:string[]; lastSecurityAudit:string; temperatureRange:string; humidityRange:string;
  cooling:CoolingType; hasVentilation:boolean; lastMaintenance:string; nextMaintenance:string;
  maintenanceNotes:string; sanitaryPermit:string|null; sanitaryPermitExpiry:string|null;
  lastInspection:string; certifications:string[]; images:WarehouseImage[]; createdAt:string; updatedAt:string|null;
}
export const STATUS_MAP: Record<WarehouseStatus,{label:string;variant:'success'|'neutral'|'warning'|'danger'}>={active:{label:'Activo',variant:'success'},full:{label:'Lleno',variant:'danger'},maintenance:{label:'Mantenimiento',variant:'warning'},inactive:{label:'Inactivo',variant:'neutral'}};
export const TYPE_LABEL:Record<WarehouseType,string>={general:'Almacén general',cold_storage:'Almacén refrigerado',hazmat:'Materiales peligrosos',transit:'Tránsito / cross-dock',bonded:'Almacén aduanal',automated:'Almacén automatizado'};
export function utilizationPct(wh:Warehouse){return wh.capacity<=0?0:Math.round((wh.used/wh.capacity)*100);}
export function utilizationColor(pct:number){return pct>=90?'239 68 68':pct>=70?'237 151 39':'0 168 107';}
export function getCapacityVariant(pct:number,status:WarehouseStatus):'success'|'warning'|'danger'|'neutral'{if(status==='maintenance'||status==='inactive')return'neutral';if(pct>=90)return'danger';if(pct>=70)return'warning';return'success';}
export function getShortWarehouseName(name:string){return name.replace(/^Almacén\s+/i,'');}
