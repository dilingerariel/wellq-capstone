# WellQ presentation API on Vercel

This deploy is an isolated synthetic demonstration, not a clinical production service. It accepts only the byte-for-byte sample in `mobile/assets/synthetic.pdf`. Do not put real patient records or PDFs in this deployment.

## Vercel project

Import the GitHub repository as a second Vercel project with Root Directory `wellq-clinical-tests-main/backend`. The FastAPI runtime discovers `index.py`; Python dependencies are in `requirements.txt`. Keep the existing portal as a separate project.

Set these API project environment variables for Production, then redeploy:

| Variable | Value |
| --- | --- |
| `ENVIRONMENT` | `test` |
| `MONGODB_DB` | `wellq_demo` |
| `MONGODB_URI` | Atlas URI; secret value, never commit it |
| `WELLQ_DEMO_AUTH_ENABLED` | `true` |
| `WELLQ_DEMO_MONGO_STORAGE_ENABLED` | `true` |
| `WELLQ_LEGACY_DEMO_LOGIN_ENABLED` | `false` (keep the old public token-minting demo endpoints closed) |
| `WELLQ_DEMO_JWT_PRIVATE_KEY` | Stable RSA private PEM; secret value |
| `JWT_ISSUER` | `https://identity.wellq-demo.invalid` |
| `JWT_AUDIENCE` | `wellq-demo` |
| `WELLQ_DEMO_PUBLIC_API_BASE_URL` | The API project's canonical HTTPS origin, without a path |
| `CORS_ORIGINS` | `["https://wellq-capstone.vercel.app"]` |
| `WELLQ_PLATFORM_ADMIN_EMAIL` | The single platform administrator's email |
| `WELLQ_PLATFORM_ADMIN_PASSWORD_HASH` | Scrypt hash; secret value, never the clear-text password |
| `AI_PROVIDER` | `gemini_api` to process the fixed synthetic presentation PDF |
| `GEMINI_API_KEY` | Gemini API key; add as a Vercel Secret, never commit it |
| `GEMINI_MODEL_ID` | `gemini-3.8-flash` (or another model enabled for the key) |
| `AI_PROVIDER_APPROVED` | `true` only to enable the synthetic-only extraction integration |

Use a dedicated MongoDB database user with only `readWrite` on `wellq_demo`. Vercel Hobby does not provide one fixed egress IP to allowlist; for this synthetic-only demo the Atlas IP rule may need `0.0.0.0/0`. This permits network attempts from any IP, so the separate database user must have a long random password and access only to `wellq_demo`. Never use this configuration for real patient data; remove the broad IP rule and rotate the database password after the presentation. Vercel static egress IPs are a paid-plan feature.

## Provision the empty database once

From `backend`, run the script and paste the URI for the dedicated Atlas app user when prompted. The input is hidden:

```powershell
.\venv\Scripts\python.exe scripts\provision_demo_atlas.py
```

The script refuses any nonempty database. This creates the tenant collections and unique indexes required by the API. The app never runs this migration automatically.

## Add account authentication to the existing demo database

If `wellq_demo` has already been provisioned and contains demo documents, do **not** rerun `provision_demo_atlas.py`. After pulling the account-auth code, run the narrow idempotent migration; it only creates `user_accounts` and its unique email index:

```powershell
.\venv\Scripts\python.exe scripts\provision_auth_accounts.py
```

Generate the administrator password hash locally (the password prompts are hidden):

```powershell
.\venv\Scripts\python.exe scripts\hash_admin_password.py
```

Add the resulting hash and the administrator email to the backend Vercel project's Production variables, then redeploy the API. Never send the password, hash, Atlas URI, or JWT private key in chat or commit them to Git.

Only patients can self-register. Their account receives a server-generated patient ID and is linked to the selected clinic and an active clinician. No public clinician-registration endpoint exists; the administrator signs in at `/admin` in the portal and creates or disables clinician accounts. Passwords use scrypt hashes, login/registration attempts are rate-limited in MongoDB, API tokens are short-lived, and browser tokens stay in memory only.

This account flow is still a synthetic demonstration: it does not verify email or a real-world patient identity. Do not deploy it for real clinical records. Production use requires an approved identity provider, verified patient onboarding, account recovery, and institutional controls.

## Portal and mobile

Set the portal Vercel project's `VITE_API_BASE_URL` to `https://<api-project>.vercel.app/api/v1`, `VITE_API_HEALTH_URL` to `https://<api-project>.vercel.app/health`, `VITE_DATA_MODE=api`, and `VITE_DEMO_AUTH_ENABLED=true`, then redeploy the portal.

Build the debug patient app with the same API host:

```powershell
flutter run --debug `
  --dart-define=WELLQ_SYNTHETIC=true `
  --dart-define=WELLQ_DEMO_IDENTITY=true `
  --dart-define=WELLQ_DEMO_ORIGIN=https://<api-project>.vercel.app `
  --dart-define=WELLQ_DEMO_HOST=<api-project>.vercel.app
```

The portal account flow is enabled by `VITE_DEMO_AUTH_ENABLED=true` in the frontend build. The patient debug build uses the patient-only registration/login flow when `WELLQ_DEMO_IDENTITY=true`. Patient login, upload link, PDF storage, download, clinic association, and clinician access checks use the Atlas-backed API. Synthetic uploads are validated by their fixed SHA-256 and size; the isolated demo does not invoke ClamAV or publish scores. If the AI settings above are enabled and the patient opted into AI processing, upload completion queues the extraction and the Vercel request processes one synthetic job with Gemini.

## AI data boundary

The Gemini Developer API integration is hard-limited in code to `mobile/assets/synthetic.pdf` (matching its fixed SHA-256 and byte length), and is disabled unless `AI_PROVIDER_APPROVED=true`. Do not put real patient PDFs in this demo. A Developer API paid tier does not use prompts to improve products, but Google's current documentation says abuse-monitoring prompts/responses may be retained for a limited period; workloads requiring guaranteed zero retention or enterprise processing agreements should use Vertex AI instead. Real clinical use therefore requires a separately approved Vertex AI adapter, cloud project, data-processing terms, and a persistent worker deployment. The demo Gemini key alone does not authorize or enable real-patient extraction.
