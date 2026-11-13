"""Two-clinic regressions: real JWT/routes, in-memory Mongo only, no live data."""

from datetime import datetime

import pytest

from app.tenancy import TenantDatabase


@pytest.mark.parametrize(
    "tenant,doctor", [("clinic-a", "doctor-a"), ("clinic-b", "doctor-b")]
)
def test_exclusive_patient_requires_its_own_clinical_relationship(
    clinics, tenant, doctor
):
    db = TenantDatabase(clinics["raw"], tenant)
    doc = db.clinical_tests.find_one({})
    doc.pop("_id")
    patient = "exclusive-" + tenant
    doc.update(
        patient_id=patient,
        clinical_test_id="exam-" + patient,
        upload={
            "upload_id": patient,
            "client_upload_id": patient,
            "status": "initiated",
        },
    )
    db.clinical_tests.insert_one(doc)
    path = "/api/v1/clinical-tests/exam-" + patient
    c = clinics["client"]
    assert c.get(path, headers=headers(clinics, tenant, patient)).status_code == 200
    assert [
        x["clinical_test_id"]
        for x in c.get(
            "/api/v1/clinical-tests", headers=headers(clinics, tenant, patient)
        ).json()["items"]
    ] == ["exam-" + patient]
    assert c.get(path, headers=headers(clinics, tenant)).status_code == 403
    hc = headers(clinics, tenant, doctor, "clinician")
    assert c.get(path, headers=hc).status_code == 403
    db.patient_access.insert_one(
        {"patient_id": patient, "authorised_clinicians": [doctor]}
    )
    assert c.get(path, headers=hc).status_code == 200
    foreign = "clinic-b" if tenant == "clinic-a" else "clinic-a"
    assert c.get(path, headers=headers(clinics, foreign, patient)).status_code == 404


@pytest.fixture
def clinics(env):
    for tenant, doctor in [("clinic-a", "doctor-a"), ("clinic-b", "doctor-b")]:
        db = TenantDatabase(env["raw"], tenant)
        db.patient_access.insert_one(
            {"patient_id": "shared-patient", "authorised_clinicians": [doctor]}
        )
        db.clinical_tests.insert_one(
            {
                "clinical_test_id": "exam-" + tenant,
                "patient_id": "shared-patient",
                "title": "SYNTHETIC " + tenant,
                "test_date": "2026-11-11",
                "deleted_at": None,
                "created_at": datetime(2026, 11, 11),
                "updated_at": datetime(2026, 11, 11),
                "file": {
                    "original_name": "synthetic.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 100,
                },
                "upload": {
                    "upload_id": tenant,
                    "client_upload_id": tenant,
                    "status": "initiated",
                },
            }
        )
    return env


def headers(env, tenant, identity="shared-patient", role="patient", **claims):
    return {
        "Authorization": "Bearer "
        + env["token"](role=role, identity=identity, tenant=tenant, **claims)
    }


@pytest.mark.parametrize("tenant", ["clinic-a", "clinic-b"])
def test_shared_patient_sees_only_current_clinic(clinics, tenant):
    response = clinics["client"].get(
        "/api/v1/clinical-tests", headers=headers(clinics, tenant)
    )
    assert response.status_code == 200, response.text
    assert [row["clinical_test_id"] for row in response.json()["items"]] == [
        "exam-" + tenant
    ]


@pytest.mark.parametrize(
    "tenant,doctor", [("clinic-a", "doctor-a"), ("clinic-b", "doctor-b")]
)
def test_authorized_clinician_reads_own_clinic_document(clinics, tenant, doctor):
    response = clinics["client"].get(
        "/api/v1/clinical-tests/exam-" + tenant,
        headers=headers(clinics, tenant, doctor, "clinician"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "SYNTHETIC " + tenant


@pytest.mark.parametrize("role", ["patient", "clinician"])
@pytest.mark.parametrize(
    "tenant,foreign,doctor",
    [
        ("clinic-a", "clinic-b", "doctor-a"),
        ("clinic-b", "clinic-a", "doctor-b"),
    ],
)
def test_cross_tenant_document_and_download_are_hidden(
    clinics, role, tenant, foreign, doctor
):
    h = headers(
        clinics, tenant, doctor if role == "clinician" else "shared-patient", role
    )
    path = "/api/v1/clinical-tests/exam-" + foreign
    assert clinics["client"].get(path, headers=h).status_code == 404
    assert clinics["client"].post(path + "/download-url", headers=h).status_code == 404


@pytest.mark.parametrize(
    "tenant,foreign_doctor", [("clinic-a", "doctor-b"), ("clinic-b", "doctor-a")]
)
def test_membership_in_other_clinic_does_not_grant_relationship(
    clinics, tenant, foreign_doctor
):
    h = headers(clinics, tenant, foreign_doctor, "clinician")
    assert (
        clinics["client"]
        .get("/api/v1/clinical-tests/exam-" + tenant, headers=h)
        .status_code
        == 403
    )


def test_other_patient_and_missing_permission_are_denied(clinics):
    path = "/api/v1/clinical-tests/exam-clinic-a"
    assert (
        clinics["client"]
        .get(path, headers=headers(clinics, "clinic-a", "other-patient"))
        .status_code
        == 403
    )
    assert (
        clinics["client"]
        .get(path, headers=headers(clinics, "clinic-a", permissions=[]))
        .status_code
        == 403
    )
    assert clinics["client"].get(path).status_code == 401


def test_scope_cannot_be_overridden_in_query_or_write(clinics):
    db = TenantDatabase(clinics["raw"], "clinic-a")
    assert db.clinical_tests.find_one({"client_id": "clinic-b"}) is None
    with pytest.raises(ValueError, match="Tenant is immutable"):
        db.clinical_tests.update_one({}, {"$set": {"client_id": "clinic-b"}})


@pytest.mark.parametrize("suffix", ["lab-score", "lab-report", "markers"])
def test_other_clinic_relationship_cannot_read_professional_results(clinics, suffix):
    h = headers(clinics, "clinic-a", "doctor-b", "clinician")
    r = clinics["client"].get(
        "/api/v1/patients/shared-patient/" + suffix,
        headers=h,
        params={"marker_codes": "glucose"} if suffix == "markers" else {},
    )
    assert r.status_code == 403
    patient = headers(clinics, "clinic-a")
    if suffix != "markers":
        assert (
            clinics["client"]
            .get("/api/v1/patients/shared-patient/" + suffix, headers=patient)
            .status_code
            == 403
        )


@pytest.mark.parametrize(
    "role,identity,tenant,status",
    [
        # PATCH scopes the lookup to the patient: hide existence with 404.
        ("patient", "other-patient", "clinic-a", 404),
        ("patient", "shared-patient", "clinic-b", 404),
        ("clinician", "doctor-a", "clinic-a", 403),
    ],
)
def test_mutations_do_not_cross_patient_tenant_or_role(
    clinics, role, identity, tenant, status
):
    r = clinics["client"].patch(
        "/api/v1/clinical-tests/exam-clinic-a",
        headers=headers(clinics, tenant, identity, role),
        json={"title": "SYNTHETIC DENIED"},
    )
    assert r.status_code == status
    assert (
        TenantDatabase(clinics["raw"], "clinic-a").clinical_tests.find_one({})["title"]
        == "SYNTHETIC clinic-a"
    )


def test_signed_download_issued_only_after_document_authorization(
    clinics, fake_storage
):
    db = TenantDatabase(clinics["raw"], "clinic-a")
    db.clinical_tests.update_one(
        {},
        {
            "$set": {
                "upload.status": "ready_for_review",
                "file.verified_at": datetime(2026, 11, 11),
                "file.generation": 1,
                "file.gcs_object_key": "private/synthetic-clinic-a.pdf",
            }
        },
    )
    path = "/api/v1/clinical-tests/exam-clinic-a/download-url"
    assert (
        clinics["client"].post(path, headers=headers(clinics, "clinic-a")).status_code
        == 200
    )
    assert (
        clinics["client"].post(path, headers=headers(clinics, "clinic-b")).status_code
        == 404
    )
    assert (
        clinics["client"]
        .post(path, headers=headers(clinics, "clinic-a", "other-patient"))
        .status_code
        == 403
    )
