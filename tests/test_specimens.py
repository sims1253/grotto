"""Specimens: every required language present, readable, role coverage."""

from pathlib import Path

import pytest

from grotto import specimens as S

REPO = Path(__file__).resolve().parents[1]


def test_all_required_languages_present():
    for lang in S.REQUIRED_LANGUAGES:
        assert lang in S.SPECIMENS, f"missing specimen for {lang}"


@pytest.mark.parametrize("lang", S.REQUIRED_LANGUAGES)
def test_every_specimen_has_role_variety(lang):
    """Each specimen must exercise several distinct roles, not just `fg`."""
    sp = S.specimen(lang)
    roles = sp.roles_used()
    assert "fg" in roles or "comment" in roles  # has some text
    assert len(roles) >= 5, f"{lang} only uses {roles}"


def test_specimens_cover_core_syntax_roles_collectively():
    """Across all specimens, the requested role variety is covered."""
    used = S.all_roles_used()
    for required in ("keyword", "string", "number", "function", "comment",
                     "operator", "punctuation", "type", "tag"):
        assert required in used, f"no specimen uses role {required!r}"


@pytest.mark.parametrize("lang", S.REQUIRED_LANGUAGES)
def test_plaintext_is_readable_and_nonempty(lang):
    sp = S.specimen(lang)
    text = sp.plaintext()
    assert text.endswith("\n")
    assert sp.line_count() >= 5
    # no stray (role, text) tuples leaked into the text
    assert "('" not in text and "tuple" not in text


def test_plaintext_roundtrips_through_spans():
    sp = S.specimen("python")
    # rebuilding from spans (joining each line's span text) yields the plaintext
    joined = "\n".join("".join(t for _, t in line) for line in sp.lines) + "\n"
    assert sp.plaintext() == joined


def test_specimen_lookup_errors_on_unknown():
    with pytest.raises(KeyError):
        S.specimen("klingon")


def test_roles_used_subset_of_spec_vocabulary():
    """Specimen roles should all be real palette role names (renderable)."""
    from grotto.spec import RoleSpec

    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    # every role used in a specimen must exist in the spec so the renderer
    # can colour it (the renderer falls back to fg otherwise, but we want the
    # specimens to use real roles).
    used = S.all_roles_used()
    unknown = sorted(used - set(roles.roles))
    assert not unknown, f"specimens use roles not in spec: {unknown}"
