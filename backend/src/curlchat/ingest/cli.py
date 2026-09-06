"""Command-line entry point for importing a local archive checkout."""

from __future__ import annotations

import argparse
from pathlib import Path

from curlchat.db.session import SessionLocal
from curlchat.ingest.archive import ArchiveImportError, import_archive


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Curling Canada player statistics.")
    parser.add_argument(
        "--source", type=Path, required=True, help="Path to the archive repository root."
    )
    arguments = parser.parse_args()

    try:
        with SessionLocal.begin() as session:
            report = import_archive(session, arguments.source)
    except ArchiveImportError as error:
        raise SystemExit(f"Import failed: {error}") from error

    print(
        "Imported "
        f"{report.yearly_statistics} yearly records for {report.players} players, "
        f"{report.aliases} aliases, and {report.events} events from {report.source_files} files; "
        f"skipped {report.skipped_aliases} conflicting aliases."
    )


if __name__ == "__main__":
    main()
