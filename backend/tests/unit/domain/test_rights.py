"""The rights a caller acts with (`.knowledge/plans/token-rights.md`): an admin right counts only
for an active admin, `documents:read` includes the numbers, no rights given means every right."""

from dataclasses import replace

from lekto.core.domain.rights import ADMIN_RIGHTS, AREA_RIGHTS, READ_RIGHTS, TokenRight, holds
from lekto.core.domain.users import Role
from tests import builders


def test_reading_the_documents_includes_counting_them() -> None:
    assert holds(frozenset({TokenRight.DOCUMENTS_READ}), TokenRight.DOCUMENTS_COUNT)
    assert not holds(frozenset({TokenRight.DOCUMENTS_COUNT}), TokenRight.DOCUMENTS_READ)
    assert not holds(frozenset(), TokenRight.DOCUMENTS_COUNT)
    assert holds(None, TokenRight.ADMIN_MANAGE)


def test_the_rights_split_into_areas_and_admin_rights() -> None:
    assert frozenset(TokenRight) == ADMIN_RIGHTS | AREA_RIGHTS
    assert not ADMIN_RIGHTS & AREA_RIGHTS
    assert all(right.value.startswith("admin:") for right in ADMIN_RIGHTS)
    assert READ_RIGHTS <= AREA_RIGHTS
    assert TokenRight.DOCUMENTS_COUNT in READ_RIGHTS
    assert TokenRight.DOCUMENTS_UPLOAD not in READ_RIGHTS


def test_an_admin_right_counts_only_for_an_active_admin() -> None:
    every = frozenset(TokenRight)
    admin = builders.admin()
    user = builders.user()
    assert admin.may(TokenRight.ADMIN_MANAGE)  # no rights given: every right of the role
    assert not user.may(TokenRight.ADMIN_MANAGE)
    assert user.may(TokenRight.DOCUMENTS_WRITE)

    admin.rights = frozenset({TokenRight.ADMIN_COUNT_ALL})
    assert admin.may(TokenRight.ADMIN_COUNT_ALL)
    assert not admin.may(TokenRight.ADMIN_DOCUMENTS_ALL)
    assert not admin.may(TokenRight.DOCUMENTS_READ)

    user.rights = every  # a token cannot make a user an admin
    assert not user.may(TokenRight.ADMIN_COUNT_ALL)
    assert user.may(TokenRight.DOCUMENTS_READ)

    admin.rights, admin.active = every, False  # a deactivated user may nothing
    assert not admin.may(TokenRight.ADMIN_MANAGE)
    assert not admin.may(TokenRight.DOCUMENTS_READ)
    assert admin.role is Role.ADMIN


def test_the_rights_are_not_part_of_the_stored_user() -> None:
    admin = builders.admin()
    acting = replace(admin, rights=frozenset())
    assert acting == admin
    assert "rights" not in repr(acting)
