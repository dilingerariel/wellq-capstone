# Synthetic Flutter → FastAPI → React handoff

Status: **prepared; the complete E2E has not run**. This is test infrastructure,
not a production identity integration or evidence that the three-client journey
already passes. Base: `f52c064993cd08e30fb3bd60c5fa109b923f15d9`.

## Intended journey

1. A new Compose project, internal network, Mongo replica set, database and four
   named volumes are created for one run. No existing volumes are mounted.
2. New private RS256 keys authorize a synthetic patient and associated clinician
   in the same synthetic tenant. The existing integration identity adapter is
   reused; no business login endpoint is added. Only that new database receives
   the synthetic clinical relationship.
3. Linux Flutter uses the actual `LoopbackIdentity`, `ApiClient`, `FileVault`,
   `LocalStore` and `UploadRepository`: queue bundled `assets/synthetic.pdf`,
   explicitly resume, reconcile, await extraction, confirm it as the patient.
   Replay the same confirmation key and retain the returned exam ID/version.
4. Playwright opens the actual React portal in `VITE_DATA_MODE=api`, selects the
   existing synthetic clinician adapter and authorized patient, then reviews and
   validates that exact exam through the normal UI. It checks the real requests'
   `expected_version` against the handoff `clinical_version` and subsequent
   version. There are no `page.route`/`fulfill` API mocks.
5. A second Flutter invocation reads the final state as the patient and checks
   private clinician notes are absent. Backend checks require one logical exam
   for the upload ID and deny another patient, unrelated clinician and tenant.

Processing, object storage, malware scanning and the clinical association adapter
use the existing **explicit integration doubles**. MongoDB and client HTTP are
real. This does not certify production GCS, ClamAV, AI, SSO or medical validity.
Patient confirmation and synthetic clinician validation remain separate stages.

## Safety gates and current blocker

The Windows orchestrator refuses reused projects/volumes/networks, occupied
loopback ports, unbounded container memory, unknown owned services/images,
foreign mounts and published Docker ports. Images must already exist and are
pinned to local image IDs; no pulls or builds run. Application source is mounted
read-only into the new stack. Only ports 8765 and 5179 bind to Windows loopback.
The Linux bridge also binds exclusively to loopback and uses private stdin/stdout
through WSL interoperability; it refuses redirects and never logs tokens.

Observed capacity on this workstation: Docker 2881 MiB; existing running service
limits total 2696 MiB. This runner reserves another 1152 MiB plus 384 MiB of
headroom: **4232 MiB total required under this conservative gate**. The check
refused execution before listeners or services were created. Existing ClamAV
and recovered services were not stopped or changed. An independently provisioned
test host, or separately authorized resource preparation, is needed. Do not
disable this check or stop recovered services to force a pass.

## Commands (PowerShell, repository root)

Controlled tests only, without Docker, WSL or HTTP servers:

```powershell
.venv/Scripts/python.exe -B -m unittest discover -s wellq-clinical-tests-main/frontend/scripts -p test_cross_client_e2e.py -v
```

Read-only capacity preflight:

```powershell
.venv/Scripts/python.exe -B wellq-clinical-tests-main/frontend/scripts/cross_client_e2e.py --check
```

Prepare private artifacts only, using a reviewed cached backend integration
image whose entrypoint is `python -B -m integration.bootstrap`:

```powershell
.venv/Scripts/python.exe -B wellq-clinical-tests-main/frontend/scripts/cross_client_e2e.py --prepare --backend-image wellq-int-39706292db88-backend
```

The command prints a new directory under ignored `.venv/wellq-cross-e2e/run-*`.
It contains private keys, generated secrets, Compose configuration and a public
mobile-source archive. Never add this directory to Git or share its contents.
Do not use `docker compose config` to print resolved credentials. Every run is
single-use; prepare again after source changes. The archive excludes ignored
files, `.runtime`, existing databases and phone data.

Only after the capacity gate passes and the installed official Linux Flutter
3.47.9, pub cache and PDFium paths have been checked, run:

```powershell
$crossRun = 'C:\Dev\wellq-capstone\.venv\wellq-cross-e2e\run-REPLACE_WITH_PREPARED_ID'
.venv/Scripts/python.exe -B wellq-clinical-tests-main/frontend/scripts/cross_client_e2e.py --run $crossRun --sdk /home/vegal/wellq-validation/phase3-5299e3/sdk/flutter --cache /home/vegal/wellq-validation/phase3-5299e3/pub-cache --pdfium /home/vegal/wellq-validation/phase3-5299e3/source/wellq-clinical-tests-main/mobile/build/native_assets/linux/libpdfium.so
```

The runner extracts a new source copy into Linux `/tmp`, runs `pub get --offline`
and only the opt-in Flutter test with `--concurrency=1`. It starts its own Vite
and runs only `playwright.cross.config.ts`. Default Flutter/Playwright discovery
skips the opt-in scenario. It never invokes `WellQ.ps1`, the habitual bridge
startup, existing integration Prepare/Start scripts, or Android/ADB.

## Evidence and cleanup

The private manifest records only synthetic IDs, versions, attempt counts and
stage results. Success requires two complete Flutter stages, the real browser
stage, denied identities, one logical exam and the final patient read. A prepared
manifest, test discovery or static analysis is **not** an E2E pass. Review private
logs locally; do not publish them without inspecting them for sensitive data.

On completion or failure, cleanup attempts independently to stop its own Vite,
loopback listener, relay and freshly identified Compose project. It does not run
`down`, `rm`, volume removal or prune. It compares the original containers'
identities, configuration, mounts, start times and restart counts. Cleanup
failures are reported; unfamiliar processes are never replaced or killed.
Synthetic test volumes and files remain available for deliberate later cleanup.
This metadata comparison does not prove the content integrity of existing data.

Not yet accredited: execution of the new E2E, runtime behavior of its Linux/WSL
relay, browser selectors against the fresh stack, production providers, or
automatic background synchronization. The production identity provider's
contract remains external and unavailable. No productive login is implemented.
