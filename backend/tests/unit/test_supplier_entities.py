"""Unit tests for supplier domain entities."""

import uuid
from app.domain.entities.supplier import Supplier, SupplierContact


def test_supplier_and_contact():
    s_uuid = uuid.uuid4()
    c = SupplierContact(id=1, supplier_id=5, full_name="Carlos Rivas", phone="+503 7000-1122")
    s = Supplier(
        id=5,
        uuid=s_uuid,
        code="PROV-001",
        name="Harinas SV",
        country_id=1,
        contacts=(c,),
    )

    assert s.id == 5
    assert s.code == "PROV-001"
    assert len(s.contacts) == 1
    assert s.contacts[0].full_name == "Carlos Rivas"
