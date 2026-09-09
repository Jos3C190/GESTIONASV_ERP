from app.domain.entities.document_general_entry import (
    clean_general_entry_name,
    normalize_general_entry_name,
)


def test_general_names_collapse_whitespace_and_unicode_case() -> None:
    cleaned = clean_general_entry_name('  Contratos   de  servicios  ')
    assert cleaned == 'Contratos de servicios'
    assert normalize_general_entry_name(' ＣＯＮＴＲＡＴＯＳ  DE servicios ') == 'contratos de servicios'


def test_general_names_reject_path_like_or_control_values() -> None:
    for value in ('', '   ', '.', '..', 'folder/name', 'folder\\name', 'bad\nname'):
        try:
            clean_general_entry_name(value)
        except ValueError:
            continue
        raise AssertionError(f'expected invalid name: {value!r}')


def test_general_names_keep_display_name_separate_from_normalized_key() -> None:
    display = clean_general_entry_name('Políticas internas')
    assert display == 'Políticas internas'
    assert normalize_general_entry_name(display) == 'políticas internas'
