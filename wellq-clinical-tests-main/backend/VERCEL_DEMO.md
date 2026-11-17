# WellQ presentation API on Vercel

This deploy is an isolated synthetic demonstration, not a clinical production service. It accepts only the byte-for-byte sample in `mobile/assets/synthetic.pdf`. Do not put real patient records or PDFs in this deployment.

## Vercel project

Import the GitHub repository as a second Vercel project with Root Directory `wellq-clinical-tests-main/backend`. The FastAPI runtime discovers `index.py`; Python dependencies are in `requirements.txt`. Keep the existing portal as a separate project.

Set these API project environment variables for Production and Preview, then redeploy:

| Variable | Value |
| --- | --- |
| `ENVIRONMENT` | `test` |
| `MONGODB_DB` | `wellq_demo` |
| `MONGODB_URI` | Atlas URI; secret value, never commit it |
| `WELLQ_DEMO_AUTH_ENABLED` | `true` |
| `WELLQ_DEMO_MONGO_STORAGE_ENABLED` | `true` |
| `WELLQ_DEMO_JWT_PRIVATE_KEY` | Stable RSA private PEM; secret value |
| `JWT_ISSUER` | `https://identity.wellq-demo.invalid` |
| `JWT_AUDIENCE` | `wellq-demo` |
| `WELLQ_DEMO_PUBLIC_API_BASE_URL` | The API project's canonical HTTPS origin, without a path |
| `CORS_ORIGINS` | `["https://wellq-capstone.vercel.app"]` |

Use a dedicated MongoDB database user with only `readWrite` on `wellq_demo`. Vercel Hobby does not provide one fixed egress IP to allowlist; for this synthetic-only demo the Atlas IP rule may need `0.0.0.0/0`. This permits network attempts from any IP, so the separate database user must have a long random password and access only to `wellq_demo`. Never use this configuration for real patient data; remove the broad IP rule and rotate the database password after the presentation. Vercel static egress IPs are a paid-plan feature.

## Provision the empty database once

From `backend`, run the script and paste the URI for the dedicated Atlas app user when prompted. The input is hidden:

```powershell
.\venv\Scripts\python.exe scripts\provision_demo_atlas.py
```

The script refuses any nonempty database. This creates the tenant collections and unique indexes required by the API. The app never runs this migration automatically.

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

The patient login, upload link, PDF storage, download, clinic association, and clinician access checks all use the Atlas-backed API. Synthetic uploads are validated by their fixed SHA-256 and size; the isolated demo does not invoke ClamAV or AI extraction and does not publish scores.
