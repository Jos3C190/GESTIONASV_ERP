from datetime import datetime

import pytest
from app.api.v1.schemas.catalog import ProductVariantConfigInput, ProductVariantUpdateInput
from app.domain.entities.product_variants import (
    ProductFamilyAttributeDraft,
    ProductFamilyAttributeValueDraft,
    ProductVariantConfigDraft,
    ProductVariantDraft,
    ProductVariantIdentifierDraft,
    ProductVariantImageDraft,
    ProductVariantUpdateDraft,
    ProductVariantValueDraft,
)
from app.domain.product_variants import (
    normalize_variant_config,
    normalize_variant_token,
    normalize_variant_update,
)
from pydantic import ValidationError


def test_variant_tokens_ignore_case_spaces_and_accents() -> None:
    assert normalize_variant_token("  Azul Marino ") == "azul-marino"
    assert normalize_variant_token("TALLA") == "talla"


def test_variant_config_normalizes_codes_and_external_image() -> None:
    config = ProductVariantConfigDraft(
        attributes=(
            ProductFamilyAttributeDraft(
                code=" Color ",
                name=" Color ",
                position=4,
                values=(ProductFamilyAttributeValueDraft(code="Rojo", label=" Rojo ", position=0),),
            ),
        ),
        variants=(
            ProductVariantDraft(
                id=None,
                sku=" CAM-ROJO ",
                name_override=" Camisa roja ",
                lifecycle_status="draft",
                values=(ProductVariantValueDraft(attribute_code=" Color ", value_code="Rojo"),),
            ),
        ),
    )
    normalized = normalize_variant_config(config)
    assert normalized.attributes[0].code == "color"
    assert normalized.variants[0].sku == "CAM-ROJO"
    assert normalized.variants[0].values[0].attribute_code == "color"


def test_variant_config_rejects_private_external_image() -> None:
    config = ProductVariantConfigDraft(
        attributes=(
            ProductFamilyAttributeDraft(
                code="color",
                name="Color",
                position=0,
                values=(ProductFamilyAttributeValueDraft(code="rojo", label="Rojo", position=0),),
            ),
        ),
        variants=(
            ProductVariantDraft(
                id=None,
                sku="CAM-ROJO",
                name_override=None,
                lifecycle_status="draft",
                values=(ProductVariantValueDraft(attribute_code="color", value_code="rojo"),),
                image=ProductVariantImageDraft(
                    source_type="external",
                    url="https://127.0.0.1/image.png",
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="direcciones privadas"):
        normalize_variant_config(config)


def test_variant_schema_accepts_sparse_matrix_without_cartesian_closure() -> None:
    payload = ProductVariantConfigInput.model_validate(
        {
            "attributes": [
                {
                    "code": "color",
                    "name": "Color",
                    "position": 0,
                    "values": [
                        {"code": "rojo", "label": "Rojo", "position": 0},
                        {"code": "azul", "label": "Azul", "position": 1},
                    ],
                },
                {
                    "code": "talla",
                    "name": "Talla",
                    "position": 1,
                    "values": [
                        {"code": "s", "label": "S", "position": 0},
                        {"code": "m", "label": "M", "position": 1},
                    ],
                },
            ],
            "variants": [
                {
                    "sku": "PAN-ROJO-S",
                    "values": [
                        {"attribute_code": "color", "value_code": "rojo"},
                        {"attribute_code": "talla", "value_code": "s"},
                    ],
                },
                {
                    "sku": "PAN-AZUL-M",
                    "values": [
                        {"attribute_code": "color", "value_code": "azul"},
                        {"attribute_code": "talla", "value_code": "m"},
                    ],
                },
            ],
        }
    )

    assert len(payload.variants) == 2


def test_variant_update_schema_requires_a_sparse_editable_field() -> None:
    with pytest.raises(ValidationError, match="al menos un campo editable"):
        ProductVariantUpdateInput.model_validate({"expected_updated_at": "2026-08-17T17:39:08Z"})


def test_variant_update_schema_rejects_combination_mutation_and_null_sku() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        ProductVariantUpdateInput.model_validate(
            {
                "values": [],
                "sku": "CAM-ROJO",
                "expected_updated_at": "2026-08-17T17:39:08Z",
            }
        )
    with pytest.raises(ValidationError, match="SKU no puede ser nulo"):
        ProductVariantUpdateInput.model_validate(
            {"sku": None, "expected_updated_at": "2026-08-17T17:39:08Z"}
        )
    with pytest.raises(ValidationError, match="zona horaria"):
        ProductVariantUpdateInput.model_validate(
            {"sku": "ABC", "expected_updated_at": "2026-08-17T17:39:08"}
        )


def test_variant_update_normalizes_only_fields_that_are_present() -> None:
    normalized = normalize_variant_update(
        ProductVariantUpdateDraft(
            expected_updated_at=datetime.fromisoformat("2026-08-17T17:39:08+00:00"),
            provided_fields=frozenset({"sku", "identifiers"}),
            sku=" CAM-ROJO ",
            identifiers=(
                ProductVariantIdentifierDraft(
                    identifier_type="ean", value=" 7501234567890 ", is_primary=True
                ),
            ),
        )
    )
    assert normalized.sku == "CAM-ROJO"
    assert normalized.identifiers is not None
    assert normalized.identifiers[0].value == "7501234567890"
    assert normalized.name_override is None


def test_variant_update_normalizes_blank_custom_name_to_none() -> None:
    normalized = normalize_variant_update(
        ProductVariantUpdateDraft(
            expected_updated_at=datetime.fromisoformat("2026-08-17T17:39:08+00:00"),
            provided_fields=frozenset({"name_override"}),
            name_override="   ",
        )
    )
    assert normalized.name_override is None
