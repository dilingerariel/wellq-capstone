"""Generate ONLY disposable synthetic credentials, never print them."""
import json
import secrets
import uuid
import shutil
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

root = Path(__file__).resolve().parent
runtime = root / ".runtime"
runtime.mkdir(exist_ok=True)
state = runtime / "state.json"
if state.exists():
    data = json.loads(state.read_text())
    assert data["project"].startswith("wellq-int-")
else:
    run = uuid.uuid4().hex[:12]
    data = {"project": "wellq-int-" + run, "run": run, "db": "wellq_integration_" + run}
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (runtime / "private.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (runtime / "public.pem").write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo))
    (runtime / "gateway.key").write_text(secrets.token_hex(32))
    env = {"WELLQ_INTEGRATION_PROJECT": data["project"], "WELLQ_INTEGRATION_RUN": run,
           "WELLQ_INTEGRATION_DB": data["db"], "WELLQ_ROOT_PASSWORD": secrets.token_hex(24),
           "WELLQ_APP_PASSWORD": secrets.token_hex(24)}
    (runtime / "integration.env").write_text("\n".join(k + "=" + v for k, v in env.items()) + "\n")
    state.write_text(json.dumps(data, indent=2))
shutil.copyfile(root.parent / "tests/test_scoring_reproducibility.py", runtime / "historical-reference.py")
print(json.dumps(data))
