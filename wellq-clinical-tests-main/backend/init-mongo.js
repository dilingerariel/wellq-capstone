db = db.getSiblingDB('wellq_clinical');

// Crear índices para clinical_tests
db.clinical_tests.createIndex({ clinical_test_id: 1 }, { unique: true });
db.clinical_tests.createIndex({ patient_id: 1, test_date: -1, created_at: -1 });
db.clinical_tests.createIndex({ "patient_id": 1, "upload.client_upload_id": 1 }, { unique: true });
db.clinical_tests.createIndex({ "upload.upload_id": 1 }, { unique: true });
db.clinical_tests.createIndex({ case_id: 1, test_date: -1 });
db.clinical_tests.createIndex({ appointment_id: 1, test_date: -1 });
db.clinical_tests.createIndex({ "upload.status": 1, updated_at: 1 });

print("✅ Índices de clinical_tests creados");