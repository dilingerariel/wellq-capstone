import os
import sys
from pathlib import Path
from integration.guard import environment, database


def configure():
    environment()
    os.environ["JWT_PUBLIC_KEY"] = Path(os.environ["JWT_PUBLIC_KEY_FILE"]).read_text()
    database()  # Refuse adapters until ownership and replica-set identity are proven.
    from integration.adapters import configure_doubles
    configure_doubles()


if __name__ == "__main__":
    configure()
    mode = sys.argv[1]
    if mode == "api":
        import uvicorn
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000, access_log=False, log_level="warning")
    elif mode == "worker":
        from app.workers.processing import main
        main()
    elif mode == "objects":
        from integration.objects import main
        main()
    elif mode == "test":
        import pytest
        raise SystemExit(pytest.main(["integration/tests", "-q", "-p", "no:cacheprovider", "--tb=short",
                                    "--junitxml=/evidence/integration.xml", *sys.argv[2:]]))
    elif mode == "clamav":
        import pytest
        raise SystemExit(pytest.main(["integration/av_checks.py", "-q", "-p", "no:cacheprovider",
                                    "--junitxml=/evidence/clamav.xml", "--tb=short"]))
    elif mode in ("restart-prepare", "restart-verify"):
        from integration.restart_probe import run
        run(mode.removeprefix("restart-"))
    elif mode == "examples":
        from integration.examples import main
        main()
    elif mode == "demo":
        from integration.demo import main
        main()
    elif mode == "demo-probes":
        from integration.functional_probes import main
        main()
    elif mode == "security-before":
        from integration.security_s01_s02 import reproduce_before
        reproduce_before()
    elif mode == "security-test":
        import pytest
        raise SystemExit(pytest.main(["integration/security_s01_s02.py", "-q", "-p", "no:cacheprovider",
            "--tb=short", "--junitxml=/evidence/integration-after.xml", *sys.argv[2:]]))
    elif mode == "review-test":
        import pytest
        raise SystemExit(pytest.main(["integration/edit_review.py", "integration/security_s01_s02.py",
            "integration/tests/test_historical_ports.py::test_endpoints_5_to_11_lifecycle",
            "integration/tests/test_f01_f07_real_db.py", "-q", "-p", "no:cacheprovider", "--tb=short",
            "--junitxml=/evidence/integration-after.xml", *sys.argv[2:]]))
    else:
        raise RuntimeError("Unknown integration operation")
