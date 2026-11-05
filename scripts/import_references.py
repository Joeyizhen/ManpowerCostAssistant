"""Import the prepared selection or switch/revert its local activation pointer."""

import argparse
import json
from pathlib import Path

from services.reference_data import root
from services.reference_import import activate, import_workbook


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook")
    parser.add_argument("--directory")
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--activate-id")
    parser.add_argument("--revert", action="store_true")
    args = parser.parse_args()
    directory = args.directory or root()
    if args.revert:
        pointer = json.loads(
            (root() if not args.directory else Path(directory))
            .joinpath("active.json")
            .read_text(encoding="utf-8")
        )
        print(json.dumps(activate(pointer["previous"], directory), indent=2))
    elif args.activate_id:
        print(json.dumps(activate(args.activate_id, directory), indent=2))
    elif args.workbook:
        snapshot = import_workbook(args.workbook, directory, args.activate)
        report = dict(snapshot["readiness_report"])
        report["pwm_review"] = {
            k: len(v) if isinstance(v, list) else v for k, v in report["pwm_review"].items()
        }
        print(json.dumps(report, indent=2))
    else:
        parser.error("Supply --workbook, --activate-id or --revert")


if __name__ == "__main__":
    main()
