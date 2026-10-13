from pipeline.gui import main
import sys
from pathlib import Path

if __name__ == "__main__":
    smoke = "--smoke-test" in sys.argv
    report = None
    if smoke:
        index = sys.argv.index("--smoke-test")
        if index + 1 >= len(sys.argv):
            raise SystemExit("--smoke-test requires a report file path")
        report = Path(sys.argv[index + 1])
    raise SystemExit(main(smoke_test=smoke, smoke_report=report))
