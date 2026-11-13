"""Standalone configuration check; no .env, tokens, sockets, DB or live fixtures."""

import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

CONFIG = Path(__file__).resolve().parents[1] / "app/config.py"


class ProductionIdentityTests(unittest.TestCase):
    def test_known_synthetic_authority_is_never_trusted_in_production(self):
        # Empty environment and working directory prevent reading local secrets,
        # including the module-level Settings instance created during import.
        # Initialize Windows cryptography before temporarily clearing its OS environment.
        public = (
            rsa.generate_private_key(public_exponent=65537, key_size=2048)
            .public_key()
            .public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )
        original = Path.cwd()
        with tempfile.TemporaryDirectory(prefix="wellq-config-test-") as directory:
            try:
                os.chdir(directory)
                with patch.dict(os.environ, {}, clear=True):
                    settings_type = runpy.run_path(str(CONFIG))["Settings"]

                    def configuration(environment, issuer, audience):
                        return settings_type(
                            _env_file=None,
                            ENVIRONMENT=environment,
                            JWT_PUBLIC_KEY=public,
                            JWT_ISSUER=issuer,
                            JWT_AUDIENCE=audience,
                            CORS_ORIGINS=[],
                        )

                    synthetic = "https://identity.wellq-integration.invalid"
                    cases = [
                        ("https://identity.wellq-capstone-demo.invalid", "example-api"),
                        ("https://identity.example.org", "wellq-capstone-demo-only"),
                        ("HTTPS://IDENTITY.WELLQ-CAPSTONE-DEMO.INVALID/", "example-api"),
                        (synthetic, "wellq-integration-only"),
                        (synthetic, "example-api"),
                        ("https://identity.example.org", "wellq-integration-only"),
                        (synthetic.upper() + "/", "example-api"),
                    ]
                    for issuer, audience in cases:
                        with (
                            self.subTest(issuer_case=issuer, audience_case=audience),
                            self.assertRaisesRegex(
                                RuntimeError, "Synthetic integration identity"
                            ),
                        ):
                            configuration(
                                "production", issuer, audience
                            ).validate_identity()
                    for environment in ("development", "test"):
                        configuration(
                            environment, synthetic, "wellq-integration-only"
                        ).validate_identity()
                    # Syntactic compatibility only: this is not provider approval.
                    configuration(
                        "production", "https://identity.example.org", "example-api"
                    ).validate_identity()
                    missing = configuration(
                        "production", "https://identity.example.org", "example-api"
                    )
                    missing.JWT_PUBLIC_KEY = None
                    with self.assertRaisesRegex(RuntimeError, "not configured"):
                        missing.validate_identity()
            finally:
                os.chdir(original)


if __name__ == "__main__":
    unittest.main()
