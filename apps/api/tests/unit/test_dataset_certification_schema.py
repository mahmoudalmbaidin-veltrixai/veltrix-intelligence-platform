"""Unit: Dataset certification is certify-gated and removed from DatasetUpdate."""

from vip_api.datasets.schemas import (
    DatasetCertifyRequest,
    DatasetRevokeCertificationRequest,
    DatasetUpdate,
)


def test_dataset_update_rejects_certification_status_field() -> None:
    assert "certification_status" not in DatasetUpdate.model_fields


def test_certify_and_revoke_request_contracts() -> None:
    certify = DatasetCertifyRequest(version=1, note="Ready for production")
    assert certify.version == 1
    assert certify.note == "Ready for production"
    revoke = DatasetRevokeCertificationRequest(version=2, note=None)
    assert revoke.version == 2
    assert revoke.note is None
