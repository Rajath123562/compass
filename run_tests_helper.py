import subprocess

with open("test_results_utf8.txt", "w", encoding="utf-8") as f:
    subprocess.run(  # noqa: PLW1510
        [".\\.venv\\Scripts\\pytest.exe", "-q", "--tb=short"], stdout=f, stderr=f
    )
