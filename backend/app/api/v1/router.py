"""API v1 router aggregation.

Phase 0: health. Phase 1: auth. Phase 1b: users. Phase 2: RBAC.
Phase 3: employees + departments. Phase 4: audit log (read-only).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import (
    audit_logs,
    auth,
    branch_product_demand,
    catalog,
    dashboard,
    departments,
    document_categories,
    document_general,
    document_general_import,
    documents,
    employee_documents,
    employees,
    expense_types,
    health,
    inventory,
    inventory_adjustments,
    inventory_kardex,
    inventory_kardex_reports,
    inventory_labels,
    inventory_lots,
    inventory_preparation,
    inventory_putaway_groups,
    inventory_trace,
    inventory_transfers,
    inventory_valuation,
    inventory_workspace,
    lifecycle,
    locations,
    media,
    operational_context,
    organization,
    product_master,
    purchase_consolidations,
    purchase_orders,
    purchase_quotations,
    purchase_requests,
    purchases,
    retaceos,
    roles,
    sales,
    supplier_master,
    suppliers,
    users,
    warehouse_receiving,
    workforce,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/api/v1")
api_router.include_router(users.router, prefix="/api/v1")
api_router.include_router(roles.router, prefix="/api/v1")
api_router.include_router(roles.me_router, prefix="/api/v1")
api_router.include_router(departments.router, prefix="/api/v1")
api_router.include_router(document_general.router, prefix="/api/v1")
api_router.include_router(document_general_import.router, prefix="/api/v1")
api_router.include_router(documents.router, prefix="/api/v1")
api_router.include_router(document_categories.router, prefix="/api/v1")
api_router.include_router(employee_documents.router, prefix="/api/v1")
api_router.include_router(employees.router, prefix="/api/v1")
api_router.include_router(workforce.router, prefix="/api/v1")
api_router.include_router(audit_logs.router, prefix="/api/v1")
api_router.include_router(organization.router, prefix="/api/v1")
api_router.include_router(branch_product_demand.router, prefix="/api/v1")
api_router.include_router(locations.router, prefix="/api/v1")
api_router.include_router(inventory.router, prefix="/api/v1")
api_router.include_router(inventory_workspace.router, prefix="/api/v1")
api_router.include_router(warehouse_receiving.router, prefix="/api/v1")
api_router.include_router(inventory_adjustments.router, prefix="/api/v1")
api_router.include_router(inventory_kardex.router, prefix="/api/v1")
api_router.include_router(inventory_kardex_reports.router, prefix="/api/v1")
api_router.include_router(inventory_labels.router, prefix="/api/v1")
api_router.include_router(inventory_preparation.router, prefix="/api/v1")
api_router.include_router(inventory_lots.router, prefix="/api/v1")
api_router.include_router(inventory_putaway_groups.router, prefix="/api/v1")
api_router.include_router(inventory_trace.router, prefix="/api/v1")
api_router.include_router(inventory_trace.public_router, prefix="/api/v1")
api_router.include_router(inventory_transfers.router, prefix="/api/v1")
api_router.include_router(inventory_valuation.router, prefix="/api/v1")
api_router.include_router(operational_context.router, prefix="/api/v1")
api_router.include_router(dashboard.router, prefix="/api/v1")
api_router.include_router(media.router, prefix="/api/v1")
api_router.include_router(catalog.router, prefix="/api/v1")
api_router.include_router(product_master.router, prefix="/api/v1")
api_router.include_router(expense_types.router, prefix="/api/v1")
api_router.include_router(purchase_orders.router, prefix="/api/v1")
api_router.include_router(purchases.order_router, prefix="/api/v1")
api_router.include_router(purchases.router, prefix="/api/v1")
api_router.include_router(retaceos.router, prefix="/api/v1")
api_router.include_router(purchase_quotations.router, prefix="/api/v1")
api_router.include_router(purchase_requests.router, prefix="/api/v1")
api_router.include_router(purchase_consolidations.router, prefix="/api/v1")
api_router.include_router(supplier_master.router, prefix="/api/v1")
api_router.include_router(sales.router, prefix="/api/v1")
api_router.include_router(suppliers.router, prefix="/api/v1")
api_router.include_router(lifecycle.router, prefix="/api/v1")
