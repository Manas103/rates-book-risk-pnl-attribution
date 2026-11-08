"""Entry point: run the relative-value screener and print every measured
claim. Mirrors scripts/run_scenarios.py's shape."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from screen import measurements


def main():
    print("=== Instrument families priced off one curve ===")
    print(json.dumps(measurements.measure_instrument_families(), indent=2, default=str))

    print("\n=== Screen: 2-sigma candidates, DV01-neutral sizing, cost-reversed direction ===")
    result = measurements.measure_screen()
    result_print = dict(result)
    print(json.dumps(result_print, indent=2, default=str))


if __name__ == "__main__":
    main()
