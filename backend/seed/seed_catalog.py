"""Dedicated seed file for catalog: countries, units, categories, subcategories, products, suppliers."""

from __future__ import annotations

import asyncio
import logging

from app.infrastructure.db.session import session_scope
from app.infrastructure.models.catalog import (
    CategoryModel,
    CompanyUnitModel,
    CountryModel,
    ProductModel,
    SubCategoryModel,
    UnitModel,
)
from app.infrastructure.models.organization import Company
from app.infrastructure.models.product_master import ProductSupplierModel
from app.infrastructure.models.supplier import SupplierContactModel, SupplierModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from seed.seed_grupo_lorena import COMPANY_ID, _restore_seed_record

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
    {
        "name": "República Dominicana",
        "iso_code_2": "DO",
        "iso_code_3": "DOM",
        "phone_code": "+1-809",
    },
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
    {
        "name": "Emiratos Árabes Unidos",
        "iso_code_2": "AE",
        "iso_code_3": "ARE",
        "phone_code": "+971",
    },
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
    {"code": "UNIT", "symbol": "u", "name": "Unidad (u)", "type": "Cantidad"},
    {"code": "BOX", "symbol": "cj", "name": "Caja (cj)", "type": "Empaque"},
    {"code": "PACK", "symbol": "pq", "name": "Paquete (pq)", "type": "Empaque"},
    {"code": "KILOGRAM", "symbol": "kg", "name": "Kilogramo (kg)", "type": "Masa"},
    {"code": "GRAM", "symbol": "g", "name": "Gramo (g)", "type": "Masa"},
    {"code": "POUND", "symbol": "lb", "name": "Libra (lb)", "type": "Masa"},
    {"code": "LITER", "symbol": "L", "name": "Litro (L)", "type": "Volumen"},
    {"code": "MILLILITER", "symbol": "mL", "name": "Mililitro (ml)", "type": "Volumen"},
    {"code": "GALLON", "symbol": "gal", "name": "Galón (gal)", "type": "Volumen"},
    {"code": "METER", "symbol": "m", "name": "Metro (m)", "type": "Longitud"},
    {"code": "CENTIMETER", "symbol": "cm", "name": "Centímetro (cm)", "type": "Longitud"},
]

CATEGORIES_DATA = [
    {
        "name": "Panadería y Repostería",
        "description": "Insumos y productos terminados de panaderías y pastelerías",
        "sub_categories": [
            "Harinas y Harinados",
            "Levaduras y Mejoradores",
            "Rellenos y Coberturas",
        ],
    },
    {
        "name": "Materia Prima Alimenticia",
        "description": "Ingredientes e insumos de producción masiva",
        "sub_categories": ["Lácteos y Derivados", "Aceites y Grasas", "Azúcar y Endulzantes"],
    },
    {
        "name": "Empaques y Desechables",
        "description": "Cajas, bolsas y envoltorios alimenticios",
        "sub_categories": [
            "Cajas de Cartón",
            "Bolsas Biodegradables",
            "Envoltorios Grado Alimenticio",
        ],
    },
    {
        "name": "Bebidas y Cafetería",
        "description": "Café en grano, jarabes y suministros de cafetería",
        "sub_categories": [
            "Café en Grano/Molido",
            "Jarabes y Saborizantes",
            "Insumos para Bebidas",
        ],
    },
]


async def seed_catalog_data(db: AsyncSession) -> None:  # noqa: C901
    logger.info("Starting Catalog & Supplier Seed Data...")
    company = await db.scalar(
        select(Company).where(Company.id == COMPANY_ID).execution_options(include_deleted=True)
    )
    if company is None:
        raise RuntimeError("Ejecute primero la semilla principal de Grupo Lorena.")
    _restore_seed_record(company)
    company_id = company.id

    # 1. Countries
    for country in COUNTRIES_DATA:
        stmt = (
            select(CountryModel)
            .where(func.lower(CountryModel.iso_code_2) == country["iso_code_2"].casefold())
            .order_by(CountryModel.created_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        existing_country = res.scalar_one_or_none()
        if existing_country is None:
            c = CountryModel(**country)
            db.add(c)
        else:
            for field, value in country.items():
                setattr(existing_country, field, value)
            existing_country.is_active = True
    await db.flush()
    logger.info("Countries seeded.")

    # Get El Salvador country ID
    es_stmt = (
        select(CountryModel)
        .where(func.lower(CountryModel.iso_code_2) == "sv")
        .order_by(CountryModel.created_at.desc())
        .limit(1)
    )
    es_res = await db.execute(es_stmt)
    es_country = es_res.scalar_one_or_none()
    country_id = es_country.id_country if es_country else 1

    # 2. Units
    units_map = {}
    for unit in UNITS_DATA:
        stmt = (
            select(UnitModel)
            .where(
                UnitModel.owner_company_id.is_(None),
                func.lower(UnitModel.code) == unit["code"].casefold(),
            )
            .order_by(UnitModel.deleted_at.asc().nullsfirst(), UnitModel.created_at.desc())
            .limit(1)
            .execution_options(include_deleted=True)
        )
        res = await db.execute(stmt)
        u = res.scalar_one_or_none()
        if not u:
            u = UnitModel(**unit, owner_company_id=None, is_standard=True)
            db.add(u)
            await db.flush()
        elif u.is_standard:
            _restore_seed_record(u)
            u.code = unit["code"]
            u.name = unit["name"]
            u.symbol = unit["symbol"]
            u.type = unit["type"]
            u.is_active = True
        else:
            raise RuntimeError(f"La unidad global {unit['code']} no es una unidad estándar.")
        config = await db.get(CompanyUnitModel, (company_id, u.id_unit))
        if config is None:
            config = CompanyUnitModel(company_id=company_id, unit_id=u.id_unit)
            db.add(config)
        config.is_enabled = True
        units_map[unit["name"]] = u.id_unit
    logger.info("Units seeded.")

    # 3. Categories & Subcategories
    cat_map = {}
    sub_map = {}
    for cat_info in CATEGORIES_DATA:
        stmt = (
            select(CategoryModel)
            .where(
                CategoryModel.company_id == company_id,
                func.lower(CategoryModel.name) == cat_info["name"].casefold(),
            )
            .order_by(CategoryModel.deleted_at.asc().nullsfirst(), CategoryModel.created_at.desc())
            .limit(1)
            .execution_options(include_deleted=True)
        )
        res = await db.execute(stmt)
        cat = res.scalar_one_or_none()
        if not cat:
            cat = CategoryModel(
                company_id=company_id, name=cat_info["name"], description=cat_info["description"]
            )
            db.add(cat)
            await db.flush()
        else:
            _restore_seed_record(cat)
            cat.description = cat_info["description"]
            cat.is_active = True
        cat_map[cat_info["name"]] = cat.id_category

        for sub_name in cat_info["sub_categories"]:
            sub_stmt = (
                select(SubCategoryModel)
                .where(
                    SubCategoryModel.id_category == cat.id_category,
                    SubCategoryModel.company_id == company_id,
                    func.lower(SubCategoryModel.name) == sub_name.casefold(),
                )
                .order_by(
                    SubCategoryModel.deleted_at.asc().nullsfirst(),
                    SubCategoryModel.created_at.desc(),
                )
                .limit(1)
                .execution_options(include_deleted=True)
            )
            sub_res = await db.execute(sub_stmt)
            sub = sub_res.scalar_one_or_none()
            if not sub:
                sub = SubCategoryModel(
                    company_id=company_id, id_category=cat.id_category, name=sub_name
                )
                db.add(sub)
                await db.flush()
            else:
                _restore_seed_record(sub)
                sub.is_active = True
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
                {
                    "full_name": "Carlos Mendoza",
                    "phone": "+503 7845-1234",
                    "email": "cmendoza@harinas.com.sv",
                },
                {
                    "full_name": "Ana María Rivas",
                    "phone": "+503 7912-8844",
                    "email": "arivas@harinas.com.sv",
                },
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
                {
                    "full_name": "Roberto Gómez",
                    "phone": "+503 7100-3322",
                    "email": "rgomez@distrilacteos.com",
                },
            ],
        },
        {
            "code": "PROV-003",
            "name": "Azúcares y Endulzantes del Valle",
            "country_id": country_id,
            "address": "Zona Industrial Santa Elena, Antiguo Cuscatlán",
            "phone": "+503 2208-0310",
            "email": "ventas@azucaresvalle.demo.sv",
            "website": None,
            "contacts": [
                {
                    "full_name": "María Fernanda Castillo",
                    "phone": "+503 7003-1103",
                    "email": "mcastillo@azucaresvalle.demo.sv",
                }
            ],
        },
        {
            "code": "PROV-004",
            "name": "Levaduras y Mejoradores Centro",
            "country_id": country_id,
            "address": "Colonia Escalón, San Salvador",
            "phone": "+503 2208-0410",
            "email": "ventas@levadurascentro.demo.sv",
            "website": None,
            "contacts": [
                {
                    "full_name": "Jorge Alberto Paredes",
                    "phone": "+503 7004-1104",
                    "email": "jparedes@levadurascentro.demo.sv",
                }
            ],
        },
        {
            "code": "PROV-005",
            "name": "Coberturas y Cacao del Pacífico",
            "country_id": country_id,
            "address": "Boulevard Merliot, Santa Tecla",
            "phone": "+503 2208-0510",
            "email": "comercial@cacaopacifico.demo.sv",
            "website": None,
            "contacts": [
                {
                    "full_name": "Daniela Hernández",
                    "phone": "+503 7005-1105",
                    "email": "dhernandez@cacaopacifico.demo.sv",
                }
            ],
        },
        {
            "code": "PROV-006",
            "name": "Rellenos Frutales Artesanales",
            "country_id": country_id,
            "address": "Carretera a San Juan Opico, La Libertad",
            "phone": "+503 2208-0610",
            "email": "pedidos@rellenosfrutales.demo.sv",
            "website": None,
            "contacts": [
                {
                    "full_name": "Luis Enrique Molina",
                    "phone": "+503 7006-1106",
                    "email": "lmolina@rellenosfrutales.demo.sv",
                }
            ],
        },
        {
            "code": "PROV-007",
            "name": "Grasas y Margarinas para Repostería",
            "country_id": country_id,
            "address": "Parque Industrial Plan de La Laguna, Antiguo Cuscatlán",
            "phone": "+503 2208-0710",
            "email": "ventas@grasasreposteria.demo.sv",
            "website": None,
            "contacts": [
                {
                    "full_name": "Patricia Elena Ruiz",
                    "phone": "+503 7007-1107",
                    "email": "pruiz@grasasreposteria.demo.sv",
                }
            ],
        },
        {
            "code": "PROV-008",
            "name": "Empaques de Cartón Centroamericanos",
            "country_id": country_id,
            "address": "Zona Industrial Soyapango, San Salvador",
            "phone": "+503 2208-0810",
            "email": "pedidos@empaquescarton.demo.sv",
            "website": None,
            "contacts": [
                {
                    "full_name": "Óscar Armando Flores",
                    "phone": "+503 7008-1108",
                    "email": "oflores@empaquescarton.demo.sv",
                }
            ],
        },
        {
            "code": "PROV-009",
            "name": "Bolsas y Empaques Biodegradables",
            "country_id": country_id,
            "address": "Zona Comercial San Marcos, San Salvador",
            "phone": "+503 2208-0910",
            "email": "ventas@bolsasbio.demo.sv",
            "website": None,
            "contacts": [
                {
                    "full_name": "Karla Beatriz Santos",
                    "phone": "+503 7009-1109",
                    "email": "ksantos@bolsasbio.demo.sv",
                }
            ],
        },
        {
            "code": "PROV-010",
            "name": "Café Tostado de Altura",
            "country_id": country_id,
            "address": "Barrio El Centro, Santa Ana",
            "phone": "+503 2208-1010",
            "email": "comercial@cafealtura.demo.sv",
            "website": None,
            "contacts": [
                {
                    "full_name": "Andrés Mauricio López",
                    "phone": "+503 7010-1110",
                    "email": "alopez@cafealtura.demo.sv",
                }
            ],
        },
        {
            "code": "PROV-011",
            "name": "Jarabes y Saborizantes del Istmo",
            "country_id": country_id,
            "address": "Colonia San Benito, San Salvador",
            "phone": "+503 2208-1110",
            "email": "pedidos@jarabersistmo.demo.sv",
            "website": None,
            "contacts": [
                {
                    "full_name": "Sofía Gabriela Núñez",
                    "phone": "+503 7011-1111",
                    "email": "snunez@jarabersistmo.demo.sv",
                }
            ],
        },
        {
            "code": "PROV-012",
            "name": "Suministros para Cafetería Lorena",
            "country_id": country_id,
            "address": "Centro Comercial Las Cascadas, Antiguo Cuscatlán",
            "phone": "+503 2208-1210",
            "email": "ventas@suministroslorena.demo.sv",
            "website": None,
            "contacts": [
                {
                    "full_name": "Ricardo Alexander Mejía",
                    "phone": "+503 7012-1112",
                    "email": "rmejia@suministroslorena.demo.sv",
                }
            ],
        },
    ]

    for sup_info in suppliers_data:
        contacts = sup_info["contacts"]
        supplier_values = {key: value for key, value in sup_info.items() if key != "contacts"}
        stmt = (
            select(SupplierModel)
            .where(
                SupplierModel.company_id == company_id,
                func.lower(SupplierModel.code) == str(sup_info["code"]).casefold(),
            )
            .order_by(SupplierModel.deleted_at.asc().nullsfirst(), SupplierModel.created_at.desc())
            .limit(1)
            .execution_options(include_deleted=True)
        )
        res = await db.execute(stmt)
        sup = res.scalar_one_or_none()
        if not sup:
            sup = SupplierModel(company_id=company_id, **supplier_values)
            db.add(sup)
            await db.flush()
        else:
            _restore_seed_record(sup)
            for field, value in supplier_values.items():
                setattr(sup, field, value)
            sup.is_active = True

        for contact in contacts:
            existing_contact = await db.scalar(
                select(SupplierContactModel)
                .where(
                    SupplierContactModel.id_supplier == sup.id_supplier,
                    func.lower(SupplierContactModel.full_name)
                    == str(contact["full_name"]).casefold(),
                )
                .order_by(
                    SupplierContactModel.deleted_at.asc().nullsfirst(),
                    SupplierContactModel.created_at.desc(),
                )
                .limit(1)
                .execution_options(include_deleted=True)
            )
            if existing_contact is None:
                existing_contact = SupplierContactModel(id_supplier=sup.id_supplier, **contact)
                db.add(existing_contact)
            else:
                _restore_seed_record(existing_contact)
                for field, value in contact.items():
                    setattr(existing_contact, field, value)
                existing_contact.is_active = True
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
        {
            "sku": "PRD-HAR-003",
            "name": "Harina Integral de Trigo 25kg",
            "id_category": cat_pan,
            "id_sub_category": sub_harina,
            "original_code": "HAR-INT-25",
            "internal_code": "INT-003",
            "purchase_unit": unit_kg,
            "sale_unit": unit_kg,
            "presentation": "Saco 25kg",
            "description": "Harina integral para panes rústicos, bollería y productos con alto contenido de fibra.",
            "weight": 25,
            "weight_unit": "kg",
            "dimension_length": 65,
            "dimension_width": 40,
            "dimension_height": 15,
            "dimension_unit": "cm",
            "variant_mode": "standalone",
        },
        {
            "sku": "PRD-AZU-004",
            "name": "Azúcar Glass Premium 10kg",
            "id_category": cat_map.get("Materia Prima Alimenticia", 1),
            "id_sub_category": sub_map.get("Azúcar y Endulzantes", 1),
            "original_code": "AZU-GLA-10",
            "internal_code": "INT-004",
            "purchase_unit": unit_cj,
            "sale_unit": unit_kg,
            "presentation": "Caja 10kg",
            "description": "Azúcar pulverizada para glaseados, rellenos y decoración de repostería.",
            "weight": 10,
            "weight_unit": "kg",
            "dimension_length": 38,
            "dimension_width": 28,
            "dimension_height": 24,
            "dimension_unit": "cm",
            "variant_mode": "standalone",
        },
        {
            "sku": "PRD-LEV-005",
            "name": "Levadura Instantánea 500g",
            "id_category": cat_pan,
            "id_sub_category": sub_map.get("Levaduras y Mejoradores", 1),
            "original_code": "LEV-INS-500",
            "internal_code": "INT-005",
            "purchase_unit": unit_cj,
            "sale_unit": unit_u,
            "presentation": "Caja 20 sobres",
            "description": "Levadura seca instantánea para fermentación uniforme en procesos de panificación.",
            "weight": 0.5,
            "weight_unit": "kg",
            "dimension_length": 22,
            "dimension_width": 16,
            "dimension_height": 12,
            "dimension_unit": "cm",
            "variant_mode": "standalone",
        },
        {
            "sku": "PRD-CHO-006",
            "name": "Chocolate de Cobertura Semiamargo 5kg",
            "id_category": cat_pan,
            "id_sub_category": sub_map.get("Rellenos y Coberturas", 1),
            "original_code": "CHO-SEM-05",
            "internal_code": "INT-006",
            "purchase_unit": unit_cj,
            "sale_unit": unit_kg,
            "presentation": "Bloque 5kg",
            "description": "Chocolate semiamargo para baños, decoraciones y elaboración de ganaches.",
            "weight": 5,
            "weight_unit": "kg",
            "dimension_length": 35,
            "dimension_width": 22,
            "dimension_height": 12,
            "dimension_unit": "cm",
            "variant_mode": "standalone",
        },
        {
            "sku": "PRD-REL-007",
            "name": "Relleno de Guayaba 4kg",
            "id_category": cat_pan,
            "id_sub_category": sub_map.get("Rellenos y Coberturas", 1),
            "original_code": "REL-GUA-04",
            "internal_code": "INT-007",
            "purchase_unit": unit_cj,
            "sale_unit": unit_kg,
            "presentation": "Cubeta 4kg",
            "description": "Relleno de guayaba listo para uso en pan dulce, tartas y pasteles.",
            "weight": 4,
            "weight_unit": "kg",
            "dimension_length": 28,
            "dimension_width": 28,
            "dimension_height": 24,
            "dimension_unit": "cm",
            "variant_mode": "standalone",
        },
        {
            "sku": "PRD-MAR-008",
            "name": "Margarina Repostera 15kg",
            "id_category": cat_map.get("Materia Prima Alimenticia", 1),
            "id_sub_category": sub_map.get("Aceites y Grasas", 1),
            "original_code": "MAR-REP-15",
            "internal_code": "INT-008",
            "purchase_unit": unit_cj,
            "sale_unit": unit_kg,
            "presentation": "Caja 15kg",
            "description": "Margarina de alto rendimiento para batidos, masas y laminados de pastelería.",
            "weight": 15,
            "weight_unit": "kg",
            "dimension_length": 45,
            "dimension_width": 30,
            "dimension_height": 22,
            "dimension_unit": "cm",
            "variant_mode": "standalone",
        },
        {
            "sku": "PRD-EMP-009",
            "name": "Caja de Cartón para Pastel 12 pulgadas",
            "id_category": cat_map.get("Empaques y Desechables", 1),
            "id_sub_category": sub_map.get("Cajas de Cartón", 1),
            "original_code": "CAJ-PAS-12",
            "internal_code": "INT-009",
            "purchase_unit": unit_cj,
            "sale_unit": unit_u,
            "presentation": "Paquete 25 unidades",
            "description": "Caja plegable de cartón grado alimenticio para pasteles de hasta 12 pulgadas.",
            "weight": 0.18,
            "weight_unit": "kg",
            "dimension_length": 33,
            "dimension_width": 33,
            "dimension_height": 15,
            "dimension_unit": "cm",
            "variant_mode": "standalone",
        },
        {
            "sku": "PRD-EMP-010",
            "name": "Bolsa Biodegradable Mediana",
            "id_category": cat_map.get("Empaques y Desechables", 1),
            "id_sub_category": sub_map.get("Bolsas Biodegradables", 1),
            "original_code": "BOL-BIO-M",
            "internal_code": "INT-010",
            "purchase_unit": unit_cj,
            "sale_unit": unit_u,
            "presentation": "Paquete 100 unidades",
            "description": "Bolsa biodegradable para despacho de panadería y productos de cafetería.",
            "weight": 0.08,
            "weight_unit": "kg",
            "dimension_length": 30,
            "dimension_width": 20,
            "dimension_height": 5,
            "dimension_unit": "cm",
            "variant_mode": "standalone",
        },
        {
            "sku": "PRD-CAF-011",
            "name": "Café Tostado y Molido 1kg",
            "id_category": cat_map.get("Bebidas y Cafetería", 1),
            "id_sub_category": sub_map.get("Café en Grano/Molido", 1),
            "original_code": "CAF-TOS-01",
            "internal_code": "INT-011",
            "purchase_unit": unit_cj,
            "sale_unit": unit_kg,
            "presentation": "Bolsa 1kg",
            "description": "Café tostado y molido de perfil balanceado para cafeterías y bebidas frías.",
            "weight": 1,
            "weight_unit": "kg",
            "dimension_length": 28,
            "dimension_width": 18,
            "dimension_height": 8,
            "dimension_unit": "cm",
            "variant_mode": "standalone",
        },
        {
            "sku": "PRD-JAR-012",
            "name": "Jarabe de Vainilla 1L",
            "id_category": cat_map.get("Bebidas y Cafetería", 1),
            "id_sub_category": sub_map.get("Jarabes y Saborizantes", 1),
            "original_code": "JAR-VAI-01",
            "internal_code": "INT-012",
            "purchase_unit": unit_cj,
            "sale_unit": unit_u,
            "presentation": "Botella 1L",
            "description": "Jarabe sabor vainilla para cafés, frappés, batidos y postres de cafetería.",
            "weight": 1.2,
            "weight_unit": "kg",
            "dimension_length": 30,
            "dimension_width": 10,
            "dimension_height": 10,
            "dimension_unit": "cm",
            "variant_mode": "standalone",
        },
    ]

    for prod in products_data:
        stmt = (
            select(ProductModel)
            .where(
                ProductModel.company_id == company_id,
                func.lower(ProductModel.sku) == str(prod["sku"]).casefold(),
            )
            .order_by(ProductModel.deleted_at.asc().nullsfirst(), ProductModel.created_at.desc())
            .limit(1)
            .execution_options(include_deleted=True)
        )
        res = await db.execute(stmt)
        product = res.scalar_one_or_none()
        if product is None:
            p = ProductModel(company_id=company_id, **prod)
            db.add(p)
        else:
            _restore_seed_record(product)
            for field, value in prod.items():
                setattr(product, field, value)
            product.is_active = True
    await db.flush()

    # 6. Supplier sourcing links for the new standalone demo products.
    # Keeping these links in the seed makes the product and supplier screens
    # useful together without creating any product variants.
    sourcing_data = [
        ("PRD-HAR-003", "PROV-001", 18.50),
        ("PRD-AZU-004", "PROV-003", 12.75),
        ("PRD-LEV-005", "PROV-004", 9.40),
        ("PRD-CHO-006", "PROV-005", 28.00),
        ("PRD-REL-007", "PROV-006", 16.25),
        ("PRD-MAR-008", "PROV-007", 31.50),
        ("PRD-EMP-009", "PROV-008", 14.00),
        ("PRD-EMP-010", "PROV-009", 6.50),
        ("PRD-CAF-011", "PROV-010", 11.75),
        ("PRD-JAR-012", "PROV-011", 8.90),
    ]
    for sku, supplier_code, unit_cost in sourcing_data:
        product = await db.scalar(
            select(ProductModel).where(
                ProductModel.company_id == company_id,
                func.lower(ProductModel.sku) == sku.casefold(),
            )
        )
        supplier = await db.scalar(
            select(SupplierModel).where(
                SupplierModel.company_id == company_id,
                func.lower(SupplierModel.code) == supplier_code.casefold(),
            )
        )
        if product is None or supplier is None:
            raise RuntimeError(f"No se pudo enlazar {sku} con {supplier_code}.")
        link = await db.scalar(
            select(ProductSupplierModel).where(
                ProductSupplierModel.company_id == company_id,
                ProductSupplierModel.product_id == product.id_product,
                ProductSupplierModel.supplier_id == supplier.id_supplier,
            )
        )
        existing_links = (
            await db.scalars(
                select(ProductSupplierModel).where(
                    ProductSupplierModel.company_id == company_id,
                    ProductSupplierModel.product_id == product.id_product,
                )
            )
        ).all()
        for existing_link in existing_links:
            if link is None or existing_link.id != link.id:
                existing_link.is_preferred = False
        await db.flush()
        if link is None:
            link = ProductSupplierModel(
                company_id=company_id,
                product_id=product.id_product,
                supplier_id=supplier.id_supplier,
            )
            db.add(link)
        link.supplier_product_code = f"{supplier_code}-{sku.removeprefix('PRD-')}"
        link.unit_cost = unit_cost
        link.currency_code = "USD"
        link.minimum_order_qty = 1
        link.order_multiple = 1
        link.lead_time_days = 3
        link.is_preferred = True
        link.status = "active"
        link.notes = "Relación demo para pruebas de abastecimiento de Grupo Lorena."
    await db.flush()
    await db.commit()
    logger.info("Products seeded successfully.")


async def main():
    async with session_scope() as session:
        await seed_catalog_data(session)


if __name__ == "__main__":
    asyncio.run(main())
