"""Platform association boundary. No local case/appointment source is assumed."""
from dataclasses import dataclass
from typing import Protocol
from fastapi import HTTPException
from app.dependencies.auth import current_identity


@dataclass(frozen=True)
class AssociationScope:
    client_id: str
    patient_id: str
    actor_id: str
    actor_role: str


@dataclass(frozen=True)
class AssociationDecision:
    kind: str
    resource_id: str
    client_id: str
    patient_id: str
    exists: bool
    authorized: bool
    active: bool
    care_relationship_valid: bool


class AssociationVerifier(Protocol):
    def verify(self, kind: str, resource_id: str, scope: AssociationScope) -> AssociationDecision:
        """Resolve from the authoritative platform, scoped to the verified actor."""
        ...


# The parent platform must inject an authorized adapter at startup.
association_verifier: AssociationVerifier | None = None


def unavailable():
    raise HTTPException(503, detail={"code": "ASSOCIATION_VERIFIER_UNAVAILABLE",
        "message": "Association verification unavailable"}, headers={"Retry-After": "2"})


def verify_associations(case_id, appointment_id, patient, db):
    resources = [(kind, value) for kind, value in (("case", case_id), ("appointment", appointment_id))
                 if value is not None]
    if not resources:
        return
    actor = current_identity.get()
    if association_verifier is None or actor is None:
        unavailable()
    if actor.client_id != db.client_id or actor.patient_id != patient or actor.role != "patient":
        raise HTTPException(403, detail={"code": "ASSOCIATION_NOT_OWNED", "message": "Association unavailable"})
    scope = AssociationScope(db.client_id, patient, actor.sub, actor.role)
    for kind, resource_id in resources:
        if not resource_id.strip() or len(resource_id) > 200:
            raise HTTPException(422, detail={"code": "INVALID_ASSOCIATION", "message": "Invalid association identifier"})
        try:
            decision = association_verifier.verify(kind, resource_id, scope)
        except Exception:
            unavailable()
        if not isinstance(decision, AssociationDecision):
            unavailable()
        if ((decision.kind, decision.resource_id, decision.client_id, decision.patient_id) !=
                (kind, resource_id, scope.client_id, scope.patient_id) or
                any(value is not True for value in (decision.exists, decision.authorized,
                    decision.active, decision.care_relationship_valid))):
            raise HTTPException(403, detail={"code": "ASSOCIATION_NOT_OWNED", "message": "Association unavailable"})
