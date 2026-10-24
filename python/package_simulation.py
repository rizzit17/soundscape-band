"""Package only project source, documentation and notebook for Colab/offline transfer."""
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / "results" / "simulation"
    out.mkdir(parents=True, exist_ok=True)
    target = out / ("soundscape-simulation-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".zip")
    patterns = ("python/*.py", "python/deda/*.py", "python/tests/*.py", "simulator/*", "notebooks/*.ipynb", "docs/SIMULATION_GUIDE.md", "c/*.c", "c/*.h", "c/Makefile")
    paths = {ROOT / "README.md", ROOT / "requirements.txt", ROOT / "Start-Simulator.cmd", ROOT / "LICENSE"}
    for pattern in patterns:
        paths.update(ROOT.glob(pattern))
    with ZipFile(target, "x", compression=ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            if path.is_file():
                archive.write(path, "soundscape-band/" + path.relative_to(ROOT).as_posix())
    print(target)
    print("Source only: no Git history, private recordings, binaries or saved experiment results included.")


if __name__ == "__main__":
    main()
