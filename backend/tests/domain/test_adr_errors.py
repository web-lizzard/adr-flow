"""ADR domain error tests."""

from domain.errors import (
    AdrAccessDenied,
    AdrEditWhileInReview,
    AdrInvalidPublishStatus,
    AdrInvalidSubmitStatus,
    AdrNotFound,
    AdrTitleAlreadyExists,
)


def test_adr_domain_errors_derive_kind_from_class_name() -> None:
    assert AdrNotFound.kind == "adr_not_found"
    assert AdrAccessDenied.kind == "adr_access_denied"
    assert AdrTitleAlreadyExists.kind == "adr_title_already_exists"
    assert AdrInvalidPublishStatus.kind == "adr_invalid_publish_status"
    assert AdrInvalidSubmitStatus.kind == "adr_invalid_submit_status"
    assert AdrEditWhileInReview.kind == "adr_edit_while_in_review"


def test_adr_domain_errors_default_to_kind_message() -> None:
    assert str(AdrNotFound()) == "adr_not_found"
    assert str(AdrTitleAlreadyExists("Title taken")) == "Title taken"
    assert (
        str(AdrInvalidPublishStatus())
        == "ADR can only be published from after_review status"
    )
    assert (
        str(AdrInvalidSubmitStatus()) == "ADR can only be submitted from draft status"
    )
    assert str(AdrEditWhileInReview()) == "Cannot edit ADR in review"
