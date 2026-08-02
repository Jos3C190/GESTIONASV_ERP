from app.application.media import cloudinary_signature


def test_cloudinary_signature_is_deterministic_and_sorted() -> None:
    expected = cloudinary_signature(
        {"timestamp": 1315060510, "public_id": "sample_image"}, "abcd"
    )
    reversed_order = cloudinary_signature(
        {"public_id": "sample_image", "timestamp": 1315060510}, "abcd"
    )
    assert expected == reversed_order
    assert len(expected) == 40


def test_cloudinary_signature_serializes_booleans_lowercase() -> None:
    assert cloudinary_signature({"invalidate": True}, "secret") == cloudinary_signature(
        {"invalidate": "true"}, "secret"
    )
