# Real clinical-document extraction (Vertex AI + ClamAV)

This is an implementation and deployment checklist for a separately reviewed
production environment. It does not turn on clinical extraction by itself.
The existing Vercel project is the synthetic demo and must not receive real
clinical PDFs.

## Processing order

1. The API creates an upload record and a private GCS quarantine object key.
2. The patient uploads directly to the signed GCS URL. The mobile app's AI
   consent is recorded with the upload.
3. The durable worker reads the object, validates the size, hash, MIME and PDF
   structure, and sends the file and each embedded PDF attachment to ClamAV.
4. Only a clean scan is promoted from quarantine to private storage. A missing
   or unreachable ClamAV service leaves the upload unapproved and retryable; it
   is never treated as a clean scan.
5. The worker queues extraction only when patient consent, production mode,
   Vertex configuration, and both explicit approval flags are present.
6. Vertex AI uses the worker's Google Application Default Credentials (ADC),
   typically an attached least-privilege runtime service account. No API key or
   downloaded service-account key is used. The response is schema-validated
   and remains a proposal for patient/clinician confirmation, not a diagnosis.

The synthetic MongoDB upload path intentionally marks malware scanning as
`not_applicable`; it accepts one fixed, non-identifying test PDF only. That path
is not eligible for real records or production extraction.

## Required service configuration

Set these only in a separately reviewed production backend and persistent
worker environment. Never add them to the frontend project:

| Variable | Purpose |
| --- | --- |
| `ENVIRONMENT=production` | Enables the production safety gates |
| `CLAMAV_HOST` / `CLAMAV_PORT` | Reachable private ClamAV daemon; normally port `3310` |
| `AI_PROVIDER=vertex_ai` | Select the Vertex adapter |
| `AI_PROVIDER_APPROVED=true` | Operational approval for the provider |
| `AI_CLINICAL_DATA_APPROVED=true` | Separate institution approval for clinical-data processing |
| `VERTEX_AI_PROJECT_ID` | GCP project with Vertex AI enabled and billing configured |
| `VERTEX_AI_LOCATION` | Explicit Vertex location supported by the selected model and approved for the data |
| `VERTEX_AI_MODEL_ID` | Model approved for extraction in that location |
| `GCS_PROJECT_ID` / `GCS_BUCKET_NAME` | Private bucket for quarantine and validated files |
| `MONGODB_URI` / `MONGODB_DB` | Production database, provisioned separately |
| trusted identity settings | Production JWT issuer/audience/JWKS, never demo identity |

Grant the runtime identity only the Vertex model invocation and required
private-bucket permissions. Do not mount a broad administrator credential.
The API and worker must share MongoDB and the private bucket. ClamAV must be
reachable only on a private network. Backups, retention, audit access, incident
response, and deletion policies must be reviewed before handling real records.

## Deployment boundary

The current Vercel synthetic project has no persistent worker loop, and the
synthetic upload route intentionally bypasses ClamAV for its fixed sample file.
It is therefore not a real-clinical deployment. The included Docker Compose
template runs API, worker, MongoDB and ClamAV together for integration work;
production still needs a hardened cloud deployment, private networking, ADC
runtime identity, health/readiness checks, durable backups, and operational
monitoring. Do not expose the ClamAV port publicly.

Before selecting the Vertex model/location, confirm current model availability
in that exact location and the clinic's approved data-residency and processing
terms. A clinic's authorization to use AI is not, by itself, confirmation of
cloud-region, retention, or contractual settings.

## Current status

The repository contains the gated Vertex adapter and ClamAV-before-promotion
worker flow. No GCP project is currently configured, so ADC, model access, and
real-document inference have not been exercised. Keep both approval flags off
until infrastructure and institutional review are complete.

ClamAV integration was checked on 2026-11-27 in an isolated Docker test stack.
The real daemon and backend worker suite passed 6/6 checks: clean-file
promotion, EICAR rejection, unavailable-scanner fail-closed behavior, and
worker state handling. The object-storage adapter was a synthetic filesystem
test double, and no patient documents were used. This does not verify the
public Vercel deployment; evidence and scope are recorded in
`reports/clamav-eicar-local-2026-11-27.md` and its pytest XML.
