# ClamAV local verification

- Date: 2026-11-27
- Target: isolated Docker integration stack, ClamAV daemon `ClamAV 1.5.5/28191`
- Method: run `integration/ClamAV.ps1` against the real ClamAV daemon and test worker
- Results:
  - **6/6 passed**, 0 failures, 0 errors, 0 skipped
  - Clean synthetic payload: approved
  - Standard harmless EICAR anti-malware test string: detected as `Eicar-Test-Signature FOUND` and rejected as `MALWARE_DETECTED`
  - Unavailable daemon: raised `ScannerUnavailable` (fail-closed)
  - Worker with clean file: promoted to `ready_for_review`
  - Worker with EICAR: rejected the document
  - Worker with unavailable daemon: kept it unapproved and recorded `DEPENDENCY_UNAVAILABLE`
- Expected outcome: the scanner detects the EICAR signature; no clinical PDF or real malware was used
- Original pytest XML: `clamav-integration-2026-11-27.xml`

## Scope

The suite ran in its dedicated Docker network and database, with real
FastAPI/worker code, MongoDB, and ClamAV; the object-storage adapter was the
declared synthetic filesystem test double. It verified that the worker
promotes a clean test document and rejects EICAR or an unavailable scanner.
No real patient document was used. This does not verify the public Vercel
deployment: the current Vercel project remains the synthetic demo and does not
run a persistent ClamAV-backed worker.
