from fastapi import APIRouter

# El endpoint #18 (GET /patients/{patient_id}/lab-score) vive en clinical_tests.py:
# solo clínico con relación verificada, sin cálculo al vuelo y con auditoría de accesos denegados.
# Este router se deja vacío para no romper el include_router de main.py.
router = APIRouter()