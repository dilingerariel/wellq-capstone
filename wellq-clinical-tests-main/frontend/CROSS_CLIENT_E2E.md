# Synthetic Flutter → FastAPI → React handoff

Status: the isolated **Flutter-engine** runner below remains prepared, not run.
The same mobile Dart clients have now completed the real HTTP/SQLite/React
handoff using the existing synthetic integration (see the low-memory path).
This does not certify the Flutter UI, Android, iOS or production providers.
Original runner base: `f52c064993cd08e30fb3bd60c5fa109b923f15d9`.

## Verified low-memory path (Windows native Dart)

`mobile/tool/patient_journey.dart` reuses the actual mobile `LoopbackIdentity`,
`ApiClient`, `UploadRepository`, `FileVault`, `LocalStore` and `ExtractionDraft`.
The HTTP layer uses the same debug/profile/product compilation constants as
Flutter, without depending on dart:ui. Production and profile identity rejection
are checked separately; the application entry point also retains `kDebugMode`.
No additional identity provider, JWT signing key or database seed is introduced.

On 2026-11-11 the existing owned project `wellq-int-39706292db88` was used:
patient login/read access; a new synthetic PDF queued in a temporary private
directory; SQLite reopen; a real signed PUT whose successful response was
deliberately dropped by the test client; explicit retry with persisted keys;
durable reception, annotated extraction and idempotent patient confirmation.
Playwright then reviewed and clinically validated that exact exam in React,
checking both `expected_version` values. A separate Dart process read the final
state and checked that professional private notes were not exposed.

This is real FastAPI HTTP and MongoDB, with the existing explicit storage,
annotated-AI and scanner doubles. It is not an Android/Flutter-widget execution
or a production integration. The response loss is deliberately injected at the
client after a real successful PUT; no existing services are fault-injected.
The original isolated runner and its resource gate are unchanged.

The tool requires a private JSON manifest: `synthetic_only: true`,
`project: "wellq-int-39706292db88"`, unique `run: "native-journey-..."`, and
`tenant`, `patient`, `clinician` from the existing verified synthetic fixture.
Do not include tokens. `upload` additionally requires `write_authorized: true`,
creates **one new exam**, and refuses a previously used manifest. `offline`
creates one separate local-only operation; `verify` checks it from a new process
with identical fields, zero attempts and intact PDF. No run deletes its files.

From `wellq-clinical-tests-main/mobile`, with the guarded bridge already ready:

```powershell
$dart = 'C:\Dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe'
# Set this to your separately prepared private synthetic manifest, not Android data.
& $dart run tool/patient_journey.dart access $manifest
# Only for an explicitly authorized NEW synthetic exam:
& $dart run tool/patient_journey.dart upload $manifest
& $dart run tool/patient_journey.dart offline $manifest
```

Then run the single existing Playwright test from `frontend`, without webServer
startup or API mocks:

```powershell
$env:WELLQ_CROSS_E2E='1'
$env:WELLQ_CROSS_MANIFEST=$manifest
$env:WELLQ_CROSS_WEB='http://127.0.0.1:5178/clinical'
node node_modules/@playwright/test/cli.js test --config playwright.cross.config.ts
```

Finally, from `mobile`: `& $dart run tool/patient_journey.dart verify $manifest`.
The browser test supports both the explicit professional sign-in gate and the
older isolated synthetic role switch. It never bypasses the session manager.
The local handoff, temporary SQLite/PDF paths and integrity evidence for the
executed run are under ignored `backend/integration/.runtime/login-repair/`.

Executed checks: access 4; upload/recovery 17; local-only pending save 6; final
patient/cold-process verification 13; one real Playwright review/validation test.
These stage counts overlap and are not a unique Flutter-test count. Existing
records and all 2,296 original objects retained their hashes. The normal API
flow added one exam, its extraction/marker, four object-store files and one
**unapproved synthetic** score snapshot in test mode. No weights, approval
flags, identity relationships or preexisting clinical records were changed.
The patient score endpoint still returned 403. Production clinical publication
requires external approval; test-mode score behavior is not medical validation.

For the actual Flutter UI, use a **separately authorized empty emulator** when
memory permits: reverse only that emulator's port 8765 to the host, then
`flutter run --debug -d emulator-<id> --dart-define=WELLQ_SYNTHETIC=true`.
Choose **Conectar paciente sintético**. Do not use `Mobile.ps1 Live` (it starts
the habitual environment), do not select the protected physical phone, and do
not interpret the native Dart handoff as emulator validation.

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
