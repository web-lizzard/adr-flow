"""ADR domain error tests."""

from domain.errors import (
    AdrAccessDenied,
    AdrInvalidPublishStatus,
    AdrNotFound,
    AdrTitleAlreadyExists,
)


def test_adr_domain_errors_derive_kind_from_class_name() -> None:
    assert AdrNotFound.kind == "adr_not_found"
    assert AdrAccessDenied.kind == "adr_access_denied"
    assert AdrTitleAlreadyExists.kind == "adr_title_already_exists"
    assert AdrInvalidPublishStatus.kind == "adr_invalid_publish_status"


def test_adr_domain_errors_default_to_kind_message() -> None:
    assert str(AdrNotFound()) == "adr_not_found"
    assert str(AdrTitleAlreadyExists("Title taken")) == "Title taken"
    assert (
        str(AdrInvalidPublishStatus())
        == "ADR can only be published from after_review status"
    )
