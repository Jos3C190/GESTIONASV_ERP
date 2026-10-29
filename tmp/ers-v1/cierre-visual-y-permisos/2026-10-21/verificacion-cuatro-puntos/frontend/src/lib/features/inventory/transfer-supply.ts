export interface TransferDemandEntry {
  id: string;
  requestId: string;
  requestCode: string;
  warehouseId: string;
  branchName: string;
  requestDate: string;
  requiredDate: string | null;
  quantity: number;
  dispatchedQuantity: number;
  remainingQuantity: number;
  statusLabel: string;
}

export interface TransferSupplyProduct {
  key: string;
  productId: number | null;
  productName: string;
  sku: string | null;
  unitId: number;
  unitLabel: string;
  availableQuantity: number;
  handlingUnitCount: number;
  requestedQuantity: number;
  pendingQuantity: number;
  reserveQuantity: number | null;
  shortageQuantity: number | null;
  canEstimateReserve: boolean;
  demands: TransferDemandEntry[];
}

export interface TransferReceiptProduct {
  key: string;
  productName: string;
  sku: string | null;
  quantity: number;
  unitLabel: string;
}

export interface TransferReceiptSummary {
  id: string;
  reference: string;
  purchaseCode: string | null;
  receivedAt: string;
  products: TransferReceiptProduct[];
}
