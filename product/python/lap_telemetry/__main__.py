"""Allow running lap-telemetry as a module: python -m lap_telemetry."""
from .cli import main
import sys

if __name__ == "__main__":
    sys.exit(main())
