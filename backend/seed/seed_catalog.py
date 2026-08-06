"""Dedicated seed file for catalog: countries, units, categories, subcategories, products, suppliers."""

from __future__ import annotations

import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import session_scope
from app.infrastructure.models.catalog import (
    CategoryModel, CountryModel, ProductModel, SubCategoryModel, UnitModel,
)
from app.infrastructure.models.supplier import SupplierContactModel, SupplierModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_catalog")

# Comprehensive ISO 3166-1 Country List (Latin American Spanish names es-SV)
COUNTRIES_DATA = [
    # América Central
    {"name": "El Salvador", "iso_code_2": "SV", "iso_code_3": "SLV", "phone_code": "+503"},
    {"name": "Guatemala", "iso_code_2": "GT", "iso_code_3": "GTM", "phone_code": "+502"},
    {"name": "Honduras", "iso_code_2": "HN", "iso_code_3": "HND", "phone_code": "+504"},
    {"name": "Nicaragua", "iso_code_2": "NI", "iso_code_3": "NIC", "phone_code": "+505"},
    {"name": "Costa Rica", "iso_code_2": "CR", "iso_code_3": "CRI", "phone_code": "+506"},
    {"name": "Panamá", "iso_code_2": "PA", "iso_code_3": "PAN", "phone_code": "+507"},
    {"name": "Belice", "iso_code_2": "BZ", "iso_code_3": "BLZ", "phone_code": "+501"},

    # América del Norte
    {"name": "México", "iso_code_2": "MX", "iso_code_3": "MEX", "phone_code": "+52"},
    {"name": "Estados Unidos", "iso_code_2": "US", "iso_code_3": "USA", "phone_code": "+1"},
    {"name": "Canadá", "iso_code_2": "CA", "iso_code_3": "CAN", "phone_code": "+1"},

    # América del Sur
    {"name": "Colombia", "iso_code_2": "CO", "iso_code_3": "COL", "phone_code": "+57"},
    {"name": "Venezuela", "iso_code_2": "VE", "iso_code_3": "VEN", "phone_code": "+58"},
    {"name": "Ecuador", "iso_code_2": "EC", "iso_code_3": "ECU", "phone_code": "+593"},
    {"name": "Perú", "iso_code_2": "PE", "iso_code_3": "PER", "phone_code": "+51"},
    {"name": "Brasil", "iso_code_2": "BR", "iso_code_3": "BRA", "phone_code": "+55"},
    {"name": "Bolivia", "iso_code_2": "BO", "iso_code_3": "BOL", "phone_code": "+591"},
    {"name": "Paraguay", "iso_code_2": "PY", "iso_code_3": "PRY", "phone_code": "+595"},
    {"name": "Chile", "iso_code_2": "CL", "iso_code_3": "CHL", "phone_code": "+56"},
    {"name": "Argentina", "iso_code_2": "AR", "iso_code_3": "ARG", "phone_code": "+54"},
    {"name": "Uruguay", "iso_code_2": "UY", "iso_code_3": "URY", "phone_code": "+598"},
    {"name": "Guyana", "iso_code_2": "GY", "iso_code_3": "GUY", "phone_code": "+592"},
    {"name": "Surinam", "iso_code_2": "SR", "iso_code_3": "SUR", "phone_code": "+597"},

    # Caribe
    {"name": "República Dominicana", "iso_code_2": "DO", "iso_code_3": "DOM", "phone_code": "+1-809"},
    {"name": "Puerto Rico", "iso_code_2": "PR", "iso_code_3": "PRI", "phone_code": "+1-787"},
    {"name": "Cuba", "iso_code_2": "CU", "iso_code_3": "CUB", "phone_code": "+53"},
    {"name": "Haití", "iso_code_2": "HT", "iso_code_3": "HTI", "phone_code": "+509"},
    {"name": "Jamaica", "iso_code_2": "JM", "iso_code_3": "JAM", "phone_code": "+1-876"},
    {"name": "Bahamas", "iso_code_2": "BS", "iso_code_3": "BHS", "phone_code": "+1-242"},
    {"name": "Barbados", "iso_code_2": "BB", "iso_code_3": "BRB", "phone_code": "+1-246"},
    {"name": "Trinidad y Tobago", "iso_code_2": "TT", "iso_code_3": "TTO", "phone_code": "+1-868"},
    {"name": "Curazao", "iso_code_2": "CW", "iso_code_3": "CUW", "phone_code": "+599"},

    # Europa
    {"name": "España", "iso_code_2": "ES", "iso_code_3": "ESP", "phone_code": "+34"},
    {"name": "Portugal", "iso_code_2": "PT", "iso_code_3": "PRT", "phone_code": "+351"},
    {"name": "Francia", "iso_code_2": "FR", "iso_code_3": "FRA", "phone_code": "+33"},
    {"name": "Italia", "iso_code_2": "IT", "iso_code_3": "ITA", "phone_code": "+39"},
    {"name": "Alemania", "iso_code_2": "DE", "iso_code_3": "DEU", "phone_code": "+49"},
    {"name": "Reino Unido", "iso_code_2": "GB", "iso_code_3": "GBR", "phone_code": "+44"},
    {"name": "Irlanda", "iso_code_2": "IE", "iso_code_3": "IRL", "phone_code": "+353"},
    {"name": "Países Bajos", "iso_code_2": "NL", "iso_code_3": "NLD", "phone_code": "+31"},
    {"name": "Bélgica", "iso_code_2": "BE", "iso_code_3": "BEL", "phone_code": "+32"},
    {"name": "Suiza", "iso_code_2": "CH", "iso_code_3": "CHE", "phone_code": "+41"},
    {"name": "Austria", "iso_code_2": "AT", "iso_code_3": "AUT", "phone_code": "+43"},
    {"name": "Suecia", "iso_code_2": "SE", "iso_code_3": "SWE", "phone_code": "+46"},
    {"name": "Noruega", "iso_code_2": "NO", "iso_code_3": "NOR", "phone_code": "+47"},
    {"name": "Dinamarca", "iso_code_2": "DK", "iso_code_3": "DNK", "phone_code": "+45"},
    {"name": "Finlandia", "iso_code_2": "FI", "iso_code_3": "FIN", "phone_code": "+358"},
    {"name": "Polonia", "iso_code_2": "PL", "iso_code_3": "POL", "phone_code": "+48"},
    {"name": "República Checa", "iso_code_2": "CZ", "iso_code_3": "CZE", "phone_code": "+420"},
    {"name": "Hungría", "iso_code_2": "HU", "iso_code_3": "HUN", "phone_code": "+36"},
    {"name": "Rumanía", "iso_code_2": "RO", "iso_code_3": "ROU", "phone_code": "+40"},
    {"name": "Grecia", "iso_code_2": "GR", "iso_code_3": "GRC", "phone_code": "+30"},
    {"name": "Turquía", "iso_code_2": "TR", "iso_code_3": "TUR", "phone_code": "+90"},
    {"name": "Rusia", "iso_code_2": "RU", "iso_code_3": "RUS", "phone_code": "+7"},

    # Asia y Medio Oriente
    {"name": "China", "iso_code_2": "CN", "iso_code_3": "CHN", "phone_code": "+86"},
    {"name": "Japón", "iso_code_2": "JP", "iso_code_3": "JPN", "phone_code": "+81"},
    {"name": "Corea del Sur", "iso_code_2": "KR", "iso_code_3": "KOR", "phone_code": "+82"},
    {"name": "India", "iso_code_2": "IN", "iso_code_3": "IND", "phone_code": "+91"},
    {"name": "Taiwán", "iso_code_2": "TW", "iso_code_3": "TWN", "phone_code": "+886"},
    {"name": "Hong Kong", "iso_code_2": "HK", "iso_code_3": "HKG", "phone_code": "+852"},
    {"name": "Singapur", "iso_code_2": "SG", "iso_code_3": "SGP", "phone_code": "+65"},
    {"name": "Vietnam", "iso_code_2": "VN", "iso_code_3": "VNM", "phone_code": "+84"},
    {"name": "Tailandia", "iso_code_2": "TH", "iso_code_3": "THA", "phone_code": "+66"},
    {"name": "Indonesia", "iso_code_2": "ID", "iso_code_3": "IDN", "phone_code": "+62"},
    {"name": "Malasia", "iso_code_2": "MY", "iso_code_3": "MYS", "phone_code": "+60"},
    {"name": "Filipinas", "iso_code_2": "PH", "iso_code_3": "PHL", "phone_code": "+63"},
    {"name": "Israel", "iso_code_2": "IL", "iso_code_3": "ISR", "phone_code": "+972"},
    {"name": "Emiratos Árabes Unidos", "iso_code_2": "AE", "iso_code_3": "ARE", "phone_code": "+971"},
    {"name": "Arabia Saudita", "iso_code_2": "SA", "iso_code_3": "SAU", "phone_code": "+966"},
    {"name": "Qatar", "iso_code_2": "QA", "iso_code_3": "QAT", "phone_code": "+974"},

    # Oceanía
    {"name": "Australia", "iso_code_2": "AU", "iso_code_3": "AUS", "phone_code": "+61"},
    {"name": "Nueva Zelanda", "iso_code_2": "NZ", "iso_code_3": "NZL", "phone_code": "+64"},

    # África
    {"name": "Sudáfrica", "iso_code_2": "ZA", "iso_code_3": "ZAF", "phone_code": "+27"},
    {"name": "Egipto", "iso_code_2": "EG", "iso_code_3": "EGY", "phone_code": "+20"},
    {"name": "Marruecos", "iso_code_2": "MA", "iso_code_3": "MAR", "phone_code": "+212"},
    {"name": "Nigeria", "iso_code_2": "NG", "iso_code_3": "NGA", "phone_code": "+234"},
    {"name": "Kenia", "iso_code_2": "KE", "iso_code_3": "KEN", "phone_code": "+254"},
]

UNITS_DATA = [
    {"name": "Unidad (u)", "type": "Cantidad"},
    {"name": "Caja (cj)", "type": "Empaque"},
    {"name": "Paquete (pq)", "type": "Empaque"},
    {"name": "Kilogramo (kg)", "type": "Masa"},
    {"name": "Gramo (g)", "type": "Masa"},
    {"name": "Libra (lb)", "type": "Masa"},
    {"name": "Litro (L)", "type": "Volumen"},
    {"name": "Mililitro (ml)", "type": "Volumen"},
    {"name": "Galón (gal)", "type": "Volumen"},
    {"name": "Metro (m)", "type": "Longitud"},
    {"name": "Centímetro (cm)", "type": "Longitud"},
]

CATEGORIES_DATA = [
    {
        "name": "Panadería y Repostería",
        "description": "Insumos y productos terminados de panaderías y pastelerías",
        "sub_categories": ["Harinas y Harinados", "Levaduras y Mejoradores", "Rellenos y Coberturas"],
    },
    {
        "name": "Materia Prima Alimenticia",
        "description": "Ingredientes e insumos de producción masiva",
        "sub_categories": ["Lácteos y Derivados", "Aceites y Grasas", "Azúcar y Endulzantes"],
    },
    {
        "name": "Empaques y Desechables",
        "description": "Cajas, bolsas y envoltorios alimenticios",
        "sub_categories": ["Cajas de Cartón", "Bolsas Biodegradables", "Envoltorios Grado Alimenticio"],
    },
    {
        "name": "Bebidas y Cafetería",
        "description": "Café en grano, jarabes y suministros de cafetería",
        "sub_categories": ["Café en Grano/Molido", "Jarabes y Saborizantes", "Insumos para Bebidas"],
    },
]


async def seed_catalog_data(db: AsyncSession) -> None:
    logger.info("Starting Catalog & Supplier Seed Data...")

    # 1. Countries
    for country in COUNTRIES_DATA:
        stmt = select(CountryModel).where(CountryModel.iso_code_2 == country["iso_code_2"])
        res = await db.execute(stmt)
        if not res.scalar_one_or_none():
            c = CountryModel(**country)
            db.add(c)
    await db.flush()
    logger.info("Countries seeded.")

    # Get El Salvador country ID
    es_stmt = select(CountryModel).where(CountryModel.iso_code_2 == "SV")
    es_res = await db.execute(es_stmt)
    es_country = es_res.scalar_one_or_none()
    country_id = es_country.id_country if es_country else 1

    # 2. Units
    units_map = {}
    for unit in UNITS_DATA:
        stmt = select(UnitModel).where(UnitModel.name == unit["name"])
        res = await db.execute(stmt)
        u = res.scalar_one_or_none()
        if not u:
            u = UnitModel(**unit)
            db.add(u)
            await db.flush()
        units_map[unit["name"]] = u.id_unit
    logger.info("Units seeded.")

    # 3. Categories & Subcategories
    cat_map = {}
    sub_map = {}
    for cat_info in CATEGORIES_DATA:
        stmt = select(CategoryModel).where(CategoryModel.name == cat_info["name"])
        res = await db.execute(stmt)
        cat = res.scalar_one_or_none()
        if not cat:
            cat = CategoryModel(name=cat_info["name"], description=cat_info["description"])
            db.add(cat)
            await db.flush()
        cat_map[cat_info["name"]] = cat.id_category

        for sub_name in cat_info["sub_categories"]:
            sub_stmt = select(SubCategoryModel).where(
                SubCategoryModel.id_category == cat.id_category,
                SubCategoryModel.name == sub_name,
            )
            sub_res = await db.execute(sub_stmt)
            sub = sub_res.scalar_one_or_none()
            if not sub:
                sub = SubCategoryModel(id_category=cat.id_category, name=sub_name)
                db.add(sub)
                await db.flush()
            sub_map[sub_name] = sub.id_sub_category
    logger.info("Categories and SubCategories seeded.")

    # 4. Demo Suppliers
    suppliers_data = [
        {
            "code": "PROV-001",
            "name": "Harinas de El Salvador S.A. de C.V.",
            "country_id": country_id,
            "address": "Km 10.5 Carretera al Puerto de La Libertad, Antiguo Cuscatlán",
            "phone": "+503 2210-4000",
            "email": "ventas@harinaselsalvador.com.sv",
            "website": "https://harinaselsalvador.com.sv",
            "contacts": [
                {"full_name": "Carlos Mendoza", "phone": "+503 7845-1234", "email": "cmendoza@harinas.com.sv"},
                {"full_name": "Ana María Rivas", "phone": "+503 7912-8844", "email": "arivas@harinas.com.sv"},
            ],
        },
        {
            "code": "PROV-002",
            "name": "Distribuidora Láctea Centroamericana",
            "country_id": country_id,
            "address": "Bulevar del Ejército Km 4.5, San Salvador",
            "phone": "+503 2250-9900",
            "email": "contacto@distrilacteos.com",
            "website": "https://distrilacteos.com",
            "contacts": [
                {"full_name": "Roberto Gómez", "phone": "+503 7100-3322", "email": "rgomez@distrilacteos.com"},
            ],
        },
    ]

    for sup_info in suppliers_data:
        contacts = sup_info.pop("contacts")
        stmt = select(SupplierModel).where(SupplierModel.code == sup_info["code"])
        res = await db.execute(stmt)
        sup = res.scalar_one_or_none()
        if not sup:
            sup = SupplierModel(**sup_info)
            db.add(sup)
            await db.flush()

            for contact in contacts:
                c_model = SupplierContactModel(id_supplier=sup.id_supplier, **contact)
                db.add(c_model)
            await db.flush()
    logger.info("Suppliers seeded.")

    # 5. Demo Products
    unit_u = units_map.get("Unidad (u)", 1)
    unit_kg = units_map.get("Kilogramo (kg)", 1)
    unit_cj = units_map.get("Caja (cj)", 1)

    cat_pan = cat_map.get("Panadería y Repostería", 1)
    sub_harina = sub_map.get("Harinas y Harinados", 1)

    products_data = [
        {
            "sku": "PRD-HAR-001",
            "name": "Harina de Trigo Suave 50lb",
            "id_category": cat_pan,
            "id_sub_category": sub_harina,
            "original_code": "HAR-SV-50",
            "internal_code": "INT-001",
            "purchase_unit": unit_kg,
            "sale_unit": unit_u,
            "presentation": "Saco 50lb",
            "description": "Harina especial para elaboración de pan dulce y repostería artesanal.",
        },
        {
            "sku": "PRD-LAC-002",
            "name": "Mantequilla Industrial sin Sal 10kg",
            "id_category": cat_map.get("Materia Prima Alimenticia", 1),
            "id_sub_category": sub_map.get("Lácteos y Derivados", 1),
            "original_code": "LAC-MAN-10",
            "internal_code": "INT-002",
            "purchase_unit": unit_cj,
            "sale_unit": unit_kg,
            "presentation": "Caja 10kg",
            "description": "Mantequilla pura de vaca para laminado de hojaldre y pastelería fina.",
        },
    ]

    for prod in products_data:
        stmt = select(ProductModel).where(ProductModel.sku == prod["sku"])
        res = await db.execute(stmt)
        if not res.scalar_one_or_none():
            p = ProductModel(**prod)
            db.add(p)
    await db.flush()
    await db.commit()
    logger.info("Products seeded successfully.")


async def main():
    async with session_scope() as session:
        await seed_catalog_data(session)


if __name__ == "__main__":
    asyncio.run(main())
