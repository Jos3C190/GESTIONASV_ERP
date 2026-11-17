"""Commercial sales documents. Physical delivery belongs to a later block."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class SalesCustomerModel(UUIDPKMixin, TimestampMixin, Base):
    """Cliente con identidad fiscal (revisión 0119).

    La base garantiza formatos y combinaciones; los requisitos completos del crédito
    fiscal los calcula el dominio (``app.domain.entities.customer``).
    """

    __tablename__ = "sales_customers"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(320))
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    customer_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="final_consumer"
    )
    taxpayer_category: Mapped[str | None] = mapped_column(String(16))
    is_withholding_agent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    person_type: Mapped[str] = mapped_column(String(1), nullable=False, server_default="1")
    commercial_name: Mapped[str | None] = mapped_column(String(200))
    document_type: Mapped[str | None] = mapped_column(String(2))
    document_number: Mapped[str | None] = mapped_column(String(20))
    nrc: Mapped[str | None] = mapped_column(String(8))
    activity_code: Mapped[str | None] = mapped_column(String(6))
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("geographic_departments.id", ondelete="RESTRICT")
    )
    municipality_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("municipalities.id", ondelete="RESTRICT")
    )
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("districts.id", ondelete="RESTRICT")
    )
    address_line: Mapped[str | None] = mapped_column(String(200))
    country_code: Mapped[str | None] = mapped_column(String(4))
    credit_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    seller_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("employees.id", ondelete="SET NULL")
    )
    is_generic: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    branch_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    #: Fecha en que se anonimizó por cancelación u olvido (revisión 0121).
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Lista de precios del cliente (revisión 0122); sin ella usa la predeterminada.
    price_list_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    #: Descuento fijo del cliente, en % (revisión 0123).
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("0")
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    updated_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_customers_company_id"),
        CheckConstraint(
            "anonymized_at IS NULL OR (NOT is_active AND NOT is_generic)",
            name="ck_sales_customers_anonymized",
        ),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["company_id", "price_list_id"],
            ["sales_price_lists.company_id", "sales_price_lists.id"],
            ondelete="RESTRICT",
            name="fk_sales_customers_price_list",
        ),
        ForeignKeyConstraint(
            ["created_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_customers_created_by_company",
        ),
        ForeignKeyConstraint(
            ["updated_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_customers_updated_by_company",
        ),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_customers_generic_branch",
        ),
        CheckConstraint(
            "customer_type IN ('final_consumer','taxpayer','foreign')",
            name="ck_sales_customers_type",
        ),
        CheckConstraint(
            "(customer_type = 'taxpayer' AND taxpayer_category IS NOT NULL "
            "AND taxpayer_category IN ('large','medium','other')) "
            "OR (customer_type <> 'taxpayer' AND taxpayer_category IS NULL)",
            name="ck_sales_customers_taxpayer_category",
        ),
        CheckConstraint("person_type IN ('1','2')", name="ck_sales_customers_person_type"),
        CheckConstraint(
            "(document_type IS NULL) = (document_number IS NULL) "
            "AND (document_type IS NULL OR document_type IN ('36','13','02','03','37')) "
            "AND (document_number IS NULL OR char_length(btrim(document_number)) >= 3)",
            name="ck_sales_customers_document",
        ),
        CheckConstraint("nrc IS NULL OR nrc ~ '^[0-9]{2,8}$'", name="ck_sales_customers_nrc"),
        CheckConstraint(
            "activity_code IS NULL OR activity_code ~ '^[0-9]{5,6}$'",
            name="ck_sales_customers_activity",
        ),
        CheckConstraint(
            "(department_id IS NULL) = (municipality_id IS NULL) "
            "AND (municipality_id IS NULL) = (district_id IS NULL)",
            name="ck_sales_customers_geography",
        ),
        CheckConstraint(
            "(customer_type = 'foreign') = (country_code IS NOT NULL) "
            "AND (customer_type <> 'foreign' OR department_id IS NULL)",
            name="ck_sales_customers_foreign",
        ),
        CheckConstraint(
            "credit_days BETWEEN 0 AND 365 AND (credit_limit IS NULL OR credit_limit >= 0)",
            name="ck_sales_customers_credit",
        ),
        CheckConstraint(
            "is_generic = (branch_id IS NOT NULL) "
            "AND (NOT is_generic OR (customer_type = 'final_consumer' "
            "AND document_type IS NULL AND nrc IS NULL))",
            name="ck_sales_customers_generic",
        ),
        Index("uq_sales_customers_company_code", "company_id", func.lower(code), unique=True),
        Index("ix_sales_customers_company_active_name", "company_id", "is_active", "name"),
        Index(
            "uq_sales_customers_generic_branch",
            "company_id",
            "branch_id",
            unique=True,
            postgresql_where=text("is_generic"),
        ),
        Index(
            "uq_sales_customers_document",
            "company_id",
            "document_type",
            "document_number",
            unique=True,
            postgresql_where=text("document_number IS NOT NULL"),
        ),
        Index(
            "uq_sales_customers_nrc",
            "company_id",
            "nrc",
            unique=True,
            postgresql_where=text("nrc IS NOT NULL"),
        ),
        Index("ix_sales_customers_company_type", "company_id", "customer_type", "is_active"),
    )


class SalesCustomerDeliveryAddressModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales_customer_delivery_addresses"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    address_line: Mapped[str] = mapped_column(String(200), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("geographic_departments.id", ondelete="RESTRICT")
    )
    municipality_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("municipalities.id", ondelete="RESTRICT")
    )
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("districts.id", ondelete="RESTRICT")
    )
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    contact_name: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(30))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        UniqueConstraint(
            "company_id", "customer_id", "id", name="uq_sales_customer_delivery_addresses_owner"
        ),
        ForeignKeyConstraint(
            ["company_id", "customer_id"],
            ["sales_customers.company_id", "sales_customers.id"],
            ondelete="CASCADE",
            name="fk_sales_customer_delivery_addresses_customer",
        ),
        CheckConstraint(
            "char_length(btrim(label)) >= 2", name="ck_sales_customer_delivery_addresses_label"
        ),
        CheckConstraint(
            "char_length(btrim(address_line)) >= 3",
            name="ck_sales_customer_delivery_addresses_line",
        ),
        CheckConstraint(
            "(department_id IS NULL) = (municipality_id IS NULL) "
            "AND (municipality_id IS NULL) = (district_id IS NULL)",
            name="ck_sales_customer_delivery_addresses_geography",
        ),
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL) "
            "AND (latitude IS NULL OR latitude BETWEEN -90 AND 90) "
            "AND (longitude IS NULL OR longitude BETWEEN -180 AND 180)",
            name="ck_sales_customer_delivery_addresses_coordinates",
        ),
        CheckConstraint(
            "NOT is_default OR is_active", name="ck_sales_customer_delivery_addresses_default"
        ),
        Index(
            "uq_sales_customer_delivery_addresses_default",
            "customer_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
        Index("ix_sales_customer_delivery_addresses_customer", "company_id", "customer_id"),
    )


def _money_column() -> Mapped[Decimal]:
    return mapped_column(Numeric(18, 2), nullable=False, server_default="0")


def _line_amount_column() -> Mapped[Decimal]:
    return mapped_column(Numeric(19, 8), nullable=False, server_default="0")


class SalesQuotationModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales_quotations"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    quotation_date: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="USD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    issued_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    # --- V2d (revisión 0124) ---
    document_type: Mapped[str] = mapped_column(String(2), nullable=False)
    price_list_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    prices_include_vat: Mapped[bool] = mapped_column(Boolean, nullable=False)
    global_discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="0"
    )
    total_not_subject: Mapped[Decimal] = _money_column()
    total_exempt: Mapped[Decimal] = _money_column()
    total_taxed: Mapped[Decimal] = _money_column()
    subtotal_sales: Mapped[Decimal] = _money_column()
    total_discount: Mapped[Decimal] = _money_column()
    vat: Mapped[Decimal] = _money_column()
    vat_perceived: Mapped[Decimal] = _money_column()
    vat_withheld: Mapped[Decimal] = _money_column()
    total_in_words: Mapped[str] = mapped_column(
        String(400), nullable=False, server_default="CERO 00/100 DÓLARES"
    )
    requires_authorization: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    authorization_reasons: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, server_default=text("'{}'")
    )
    authorized_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authorization_note: Mapped[str | None] = mapped_column(Text)
    customer_response_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    customer_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_quotations_company_id"),
        UniqueConstraint("company_id", "code", name="uq_sales_quotations_company_code"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_quotations_branch_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "customer_id"],
            ["sales_customers.company_id", "sales_customers.id"],
            ondelete="RESTRICT",
            name="fk_sales_quotations_customer_company",
        ),
        ForeignKeyConstraint(
            ["created_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_quotations_creator_company",
        ),
        ForeignKeyConstraint(
            ["issued_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_quotations_issuer_company",
        ),
        ForeignKeyConstraint(
            ["authorized_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_quotations_authorizer_company",
        ),
        ForeignKeyConstraint(
            ["customer_response_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_quotations_responder_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "price_list_id"],
            ["sales_price_lists.company_id", "sales_price_lists.id"],
            ondelete="RESTRICT",
            name="fk_sales_quotations_price_list",
        ),
        ForeignKeyConstraint(
            ["cancelled_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_quotations_canceller_company",
        ),
        CheckConstraint("currency = 'USD'", name="ck_sales_quotations_currency_usd"),
        CheckConstraint(
            "status IN ('draft','pending_authorization','issued','accepted','rejected','cancelled')",
            name="ck_sales_quotations_status",
        ),
        CheckConstraint("document_type IN ('01','03')", name="ck_sales_quotations_document"),
        CheckConstraint(
            "version >= 1 AND valid_until >= quotation_date",
            name="ck_sales_quotations_dates_version",
        ),
        CheckConstraint(
            "global_discount_percent >= 0 AND global_discount_percent <= 100",
            name="ck_sales_quotations_global_discount",
        ),
        CheckConstraint(
            "total_not_subject >= 0 AND total_exempt >= 0 AND total_taxed >= 0 "
            "AND subtotal_sales >= 0 AND total_discount >= 0 AND subtotal >= 0 "
            "AND vat >= 0 AND vat_perceived >= 0 AND vat_withheld >= 0 AND total >= 0",
            name="ck_sales_quotations_totals",
        ),
        CheckConstraint(
            "(issued_at IS NULL) = (issued_by_id IS NULL) "
            "AND (status NOT IN ('issued','accepted','rejected') OR issued_at IS NOT NULL) "
            "AND (status NOT IN ('draft','pending_authorization') OR issued_at IS NULL)",
            name="ck_sales_quotations_issue",
        ),
        CheckConstraint(
            "(authorized_at IS NULL) = (authorized_by_id IS NULL)",
            name="ck_sales_quotations_authorization",
        ),
        CheckConstraint(
            "(customer_response_at IS NULL) = (customer_response_by_id IS NULL) "
            "AND (status NOT IN ('accepted','rejected') OR customer_response_at IS NOT NULL) "
            "AND (status NOT IN ('draft','pending_authorization','issued') "
            "OR customer_response_at IS NULL) "
            "AND (status = 'rejected') = (rejection_reason IS NOT NULL)",
            name="ck_sales_quotations_response",
        ),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL AND cancelled_by_id IS NOT NULL AND cancellation_reason IS NOT NULL)",
            name="ck_sales_quotations_cancellation",
        ),
        Index(
            "ix_sales_quotations_company_branch_status_date",
            "company_id",
            "branch_id",
            "status",
            "quotation_date",
        ),
        Index(
            "ix_sales_quotations_company_customer", "company_id", "customer_id", "quotation_date"
        ),
    )


class SalesQuotationLineModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales_quotation_lines"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    quotation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    packaging_definition_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    packaging_version: Mapped[int | None] = mapped_column(Integer)
    unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    base_unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    product_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_unit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    # --- V2d (revisión 0124) ---
    price_list_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    list_price: Mapped[Decimal | None] = mapped_column(Numeric(19, 8))
    price_overridden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="0"
    )
    suggested_discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="0"
    )
    suggested_discount_source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="none"
    )
    tax_treatment: Mapped[str] = mapped_column(String(16), nullable=False)
    item_type: Mapped[str] = mapped_column(String(1), nullable=False)
    document_unit_price: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    discount_amount: Mapped[Decimal] = _line_amount_column()
    not_subject: Mapped[Decimal] = _line_amount_column()
    exempt: Mapped[Decimal] = _line_amount_column()
    taxed: Mapped[Decimal] = _line_amount_column()
    vat_item: Mapped[Decimal | None] = mapped_column(Numeric(19, 8))
    cost: Mapped[Decimal | None] = mapped_column(Numeric(19, 8))
    margin_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    authorization_reasons: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, server_default=text("'{}'")
    )

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_quotation_lines_company_id"),
        UniqueConstraint(
            "company_id", "quotation_id", "line_number", name="uq_sales_quotation_lines_number"
        ),
        ForeignKeyConstraint(
            ["company_id", "quotation_id"],
            ["sales_quotations.company_id", "sales_quotations.id"],
            ondelete="CASCADE",
            name="fk_sales_quotation_lines_header_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            ondelete="RESTRICT",
            name="fk_sales_quotation_lines_product_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id", "variant_id"],
            ["product_variants.company_id", "product_variants.product_id", "product_variants.id"],
            ondelete="RESTRICT",
            name="fk_sales_quotation_lines_variant_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
            name="fk_sales_quotation_lines_item_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "packaging_definition_id"],
            [
                "inventory_packaging_definitions.company_id",
                "inventory_packaging_definitions.inventory_item_id",
                "inventory_packaging_definitions.id",
            ],
            ondelete="RESTRICT",
            name="fk_sales_quotation_lines_packaging",
        ),
        ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            ondelete="RESTRICT",
            name="fk_sales_quotation_lines_unit_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "base_unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            ondelete="RESTRICT",
            name="fk_sales_quotation_lines_base_unit_company",
        ),
        CheckConstraint(
            "line_number > 0 AND quantity > 0 AND quantity_base > 0 AND unit_factor > 0",
            name="ck_sales_quotation_lines_quantities",
        ),
        CheckConstraint(
            "unit_price >= 0 AND line_total >= 0 AND document_unit_price >= 0 "
            "AND discount_amount >= 0 AND not_subject >= 0 AND exempt >= 0 AND taxed >= 0 "
            "AND (list_price IS NULL OR list_price >= 0) AND (cost IS NULL OR cost >= 0)",
            name="ck_sales_quotation_lines_amounts",
        ),
        CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100 "
            "AND suggested_discount_percent >= 0 AND suggested_discount_percent <= 100 "
            "AND suggested_discount_source IN ('none','customer','volume')",
            name="ck_sales_quotation_lines_discounts",
        ),
        CheckConstraint(
            "tax_treatment IN ('taxed','exempt','not_subject') AND item_type IN ('1','2','3')",
            name="ck_sales_quotation_lines_tax",
        ),
        CheckConstraint(
            "price_overridden OR list_price IS NOT NULL",
            name="ck_sales_quotation_lines_price_source",
        ),
        ForeignKeyConstraint(
            ["company_id", "price_list_id"],
            ["sales_price_lists.company_id", "sales_price_lists.id"],
            ondelete="RESTRICT",
            name="fk_sales_quotation_lines_price_list",
        ),
        CheckConstraint(
            "(packaging_definition_id IS NULL) = (packaging_version IS NULL)",
            name="ck_sales_quotation_lines_packaging_snapshot",
        ),
    )


class SaleModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    quotation_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="USD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    confirmed_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    # --- V2e (revisión 0125) ---
    document_type: Mapped[str] = mapped_column(String(2), nullable=False)
    price_list_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    prices_include_vat: Mapped[bool] = mapped_column(Boolean, nullable=False)
    global_discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="0"
    )
    total_not_subject: Mapped[Decimal] = _money_column()
    total_exempt: Mapped[Decimal] = _money_column()
    total_taxed: Mapped[Decimal] = _money_column()
    subtotal_sales: Mapped[Decimal] = _money_column()
    total_discount: Mapped[Decimal] = _money_column()
    vat: Mapped[Decimal] = _money_column()
    vat_perceived: Mapped[Decimal] = _money_column()
    vat_withheld: Mapped[Decimal] = _money_column()
    total_in_words: Mapped[str] = mapped_column(
        String(400), nullable=False, server_default="CERO 00/100 DÓLARES"
    )
    requires_authorization: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    authorization_reasons: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, server_default=text("'{}'")
    )
    authorized_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authorization_note: Mapped[str | None] = mapped_column(Text)
    promised_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    delivery_address_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    delivery_address_text: Mapped[str | None] = mapped_column(String(400))
    payment_terms: Mapped[str] = mapped_column(String(8), nullable=False)
    credit_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_company_id"),
        UniqueConstraint("company_id", "code", name="uq_sales_company_code"),
        UniqueConstraint("company_id", "quotation_id", name="uq_sales_source_quotation"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_branch_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "customer_id"],
            ["sales_customers.company_id", "sales_customers.id"],
            ondelete="RESTRICT",
            name="fk_sales_customer_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "quotation_id"],
            ["sales_quotations.company_id", "sales_quotations.id"],
            ondelete="RESTRICT",
            name="fk_sales_source_quotation_company",
        ),
        ForeignKeyConstraint(
            ["created_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_creator_company",
        ),
        ForeignKeyConstraint(
            ["confirmed_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_confirmer_company",
        ),
        ForeignKeyConstraint(
            ["cancelled_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_canceller_company",
        ),
        CheckConstraint("currency = 'USD'", name="ck_sales_currency_usd"),
        ForeignKeyConstraint(
            ["company_id", "price_list_id"],
            ["sales_price_lists.company_id", "sales_price_lists.id"],
            ondelete="RESTRICT",
            name="fk_sales_price_list",
        ),
        ForeignKeyConstraint(
            ["authorized_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_authorizer_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "customer_id", "delivery_address_id"],
            [
                "sales_customer_delivery_addresses.company_id",
                "sales_customer_delivery_addresses.customer_id",
                "sales_customer_delivery_addresses.id",
            ],
            ondelete="RESTRICT",
            name="fk_sales_delivery_address",
        ),
        CheckConstraint(
            "status IN ('draft','pending_authorization','confirmed','cancelled')",
            name="ck_sales_status",
        ),
        CheckConstraint("document_type IN ('01','03')", name="ck_sales_document"),
        CheckConstraint(
            "global_discount_percent >= 0 AND global_discount_percent <= 100",
            name="ck_sales_global_discount",
        ),
        CheckConstraint(
            "version >= 1 "
            "AND total_not_subject >= 0 AND total_exempt >= 0 AND total_taxed >= 0 "
            "AND subtotal_sales >= 0 AND total_discount >= 0 AND subtotal >= 0 "
            "AND vat >= 0 AND vat_perceived >= 0 AND vat_withheld >= 0 AND total >= 0",
            name="ck_sales_totals_version",
        ),
        CheckConstraint(
            "(confirmed_at IS NULL) = (confirmed_by_id IS NULL) "
            "AND (status <> 'confirmed' OR confirmed_at IS NOT NULL) "
            "AND (status NOT IN ('draft','pending_authorization') OR confirmed_at IS NULL)",
            name="ck_sales_confirmation",
        ),
        CheckConstraint(
            "(authorized_at IS NULL) = (authorized_by_id IS NULL)",
            name="ck_sales_authorization",
        ),
        CheckConstraint(
            "delivery_mode IN ('pickup','delivery') "
            "AND (delivery_mode = 'delivery') = (delivery_address_id IS NOT NULL) "
            "AND (delivery_address_id IS NULL) = (delivery_address_text IS NULL)",
            name="ck_sales_delivery",
        ),
        CheckConstraint(
            "payment_terms IN ('cash','credit') AND credit_days BETWEEN 0 AND 365 "
            "AND (payment_terms = 'credit' OR credit_days = 0)",
            name="ck_sales_payment",
        ),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL AND cancelled_by_id IS NOT NULL AND cancellation_reason IS NOT NULL)",
            name="ck_sales_cancellation",
        ),
        Index(
            "ix_sales_company_branch_status_created",
            "company_id",
            "branch_id",
            "status",
            "created_at",
        ),
    )


class SaleLineModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales_lines"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sale_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_quotation_line_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    packaging_definition_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    packaging_version: Mapped[int | None] = mapped_column(Integer)
    unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    base_unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    product_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_unit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    # --- V2e (revisión 0125) ---
    price_list_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    list_price: Mapped[Decimal | None] = mapped_column(Numeric(19, 8))
    price_overridden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="0"
    )
    suggested_discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="0"
    )
    suggested_discount_source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="none"
    )
    tax_treatment: Mapped[str] = mapped_column(String(16), nullable=False)
    item_type: Mapped[str] = mapped_column(String(1), nullable=False)
    document_unit_price: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    discount_amount: Mapped[Decimal] = _line_amount_column()
    not_subject: Mapped[Decimal] = _line_amount_column()
    exempt: Mapped[Decimal] = _line_amount_column()
    taxed: Mapped[Decimal] = _line_amount_column()
    vat_item: Mapped[Decimal | None] = mapped_column(Numeric(19, 8))
    cost: Mapped[Decimal | None] = mapped_column(Numeric(19, 8))
    margin_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    authorization_reasons: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, server_default=text("'{}'")
    )

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_lines_company_id"),
        UniqueConstraint("company_id", "sale_id", "id", name="uq_sales_lines_company_sale_id"),
        UniqueConstraint("company_id", "sale_id", "line_number", name="uq_sales_lines_number"),
        UniqueConstraint(
            "company_id", "source_quotation_line_id", name="uq_sales_lines_source_quote_line"
        ),
        ForeignKeyConstraint(
            ["company_id", "sale_id"],
            ["sales.company_id", "sales.id"],
            ondelete="CASCADE",
            name="fk_sales_lines_header_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "source_quotation_line_id"],
            ["sales_quotation_lines.company_id", "sales_quotation_lines.id"],
            ondelete="RESTRICT",
            name="fk_sales_lines_source_quote_line",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            ondelete="RESTRICT",
            name="fk_sales_lines_product_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id", "variant_id"],
            ["product_variants.company_id", "product_variants.product_id", "product_variants.id"],
            ondelete="RESTRICT",
            name="fk_sales_lines_variant_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
            name="fk_sales_lines_item_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "packaging_definition_id"],
            [
                "inventory_packaging_definitions.company_id",
                "inventory_packaging_definitions.inventory_item_id",
                "inventory_packaging_definitions.id",
            ],
            ondelete="RESTRICT",
            name="fk_sales_lines_packaging",
        ),
        ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            ondelete="RESTRICT",
            name="fk_sales_lines_unit_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "base_unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            ondelete="RESTRICT",
            name="fk_sales_lines_base_unit_company",
        ),
        CheckConstraint(
            "line_number > 0 AND quantity > 0 AND quantity_base > 0 AND unit_factor > 0",
            name="ck_sales_lines_quantities",
        ),
        ForeignKeyConstraint(
            ["company_id", "price_list_id"],
            ["sales_price_lists.company_id", "sales_price_lists.id"],
            ondelete="RESTRICT",
            name="fk_sales_lines_price_list",
        ),
        CheckConstraint(
            "unit_price >= 0 AND line_total >= 0 AND document_unit_price >= 0 "
            "AND discount_amount >= 0 AND not_subject >= 0 AND exempt >= 0 AND taxed >= 0 "
            "AND (list_price IS NULL OR list_price >= 0) AND (cost IS NULL OR cost >= 0)",
            name="ck_sales_lines_amounts",
        ),
        CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100 "
            "AND suggested_discount_percent >= 0 AND suggested_discount_percent <= 100 "
            "AND suggested_discount_source IN ('none','customer','volume')",
            name="ck_sales_lines_discounts",
        ),
        CheckConstraint(
            "tax_treatment IN ('taxed','exempt','not_subject') AND item_type IN ('1','2','3')",
            name="ck_sales_lines_tax",
        ),
        CheckConstraint(
            "price_overridden OR list_price IS NOT NULL",
            name="ck_sales_lines_price_source",
        ),
        Index("ix_sales_lines_reservation", "company_id", "inventory_item_id", "sale_id"),
        CheckConstraint(
            "(packaging_definition_id IS NULL) = (packaging_version IS NULL)",
            name="ck_sales_lines_packaging_snapshot",
        ),
    )


class SalesIdempotencyModel(UUIDPKMixin, Base):
    __tablename__ = "sales_idempotency_commands"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(24), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "action", "idempotency_key", name="uq_sales_idempotency_action_key"
        ),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["actor_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_idempotency_actor_company",
        ),
        CheckConstraint(
            "resource_type IN ('quotation','sale')", name="ck_sales_idempotency_resource_type"
        ),
    )
