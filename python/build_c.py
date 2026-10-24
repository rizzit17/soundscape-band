"""Optional cross-platform GCC/Clang host build for the C/Python equivalence tests."""
import os
from pathlib import Path
import shutil
import subprocess


def main():
    cc = shutil.which("gcc") or shutil.which("clang") or shutil.which("cc")
    if cc is None:
        raise SystemExit("No C compiler found. The browser simulator only needs Python; skip this optional step.")
    directory = Path(__file__).resolve().parents[1] / "c"
    suffix = ".exe" if os.name == "nt" else ""
    for precision in ("double", "float"):
        output = directory / f"deda_host_{precision}{suffix}"
        command = [cc, "-std=c99", "-O2", "-Wall", "-Wextra", f"-DDEDA_REAL={precision}",
                   "-o", str(output), "deda.c", "doa_gcc.c", "host_main.c", "-lm"]
        subprocess.run(command, cwd=directory, check=True)
        print(f"Built {output}")


if __name__ == "__main__":
    main()
