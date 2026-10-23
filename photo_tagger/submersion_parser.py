"""Parser for Submersion dive log databases (submersion.db)"""

import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .subsurface_parser import Dive, DiveSite

logger = logging.getLogger(__name__)

SQLITE_HEADER = b'SQLite format 3\x00'


def is_sqlite_file(file_path: str) -> bool:
    """Return True if the file starts with the SQLite header"""
    try:
        with open(file_path, 'rb') as f:
            return f.read(len(SQLITE_HEADER)) == SQLITE_HEADER
    except OSError:
        return False


class SubmersionParser:
    """Parser for the SQLite database used by the Submersion dive log app.

    Submersion stores dive times as epoch milliseconds whose UTC components are
    the dive computer's wall clock, so they are decoded as UTC and returned as
    naive datetimes to compare directly against camera EXIF times.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path

    def parse(self) -> list[Dive]:
        """Parse the Submersion database and return list of dives"""
        path = Path(self.file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Submersion database not found: {self.file_path}")

        # Read-only so the app's live database is never modified. Not
        # immutable, so SQLite still applies any pending -wal changes.
        uri = path.resolve().as_uri() + '?mode=ro'
        try:
            conn = sqlite3.connect(uri, uri=True)
        except sqlite3.Error as e:
            raise ValueError(f"Could not open Submersion database: {e}")

        try:
            conn.row_factory = sqlite3.Row
            sites = self._parse_dive_sites(conn)
            tags = self._parse_dive_tags(conn)
            return self._parse_dives(conn, sites, tags)
        except sqlite3.DatabaseError as e:
            raise ValueError(
                f"Could not read Submersion database ({e}). If database "
                "encryption is enabled in Submersion it must be disabled."
            )
        finally:
            conn.close()

    def _parse_dive_sites(self, conn: sqlite3.Connection) -> dict[str, DiveSite]:
        """Parse dive sites keyed by site id"""
        sites = {}
        for row in conn.execute('SELECT * FROM dive_sites'):
            row = dict(row)
            sites[row['id']] = DiveSite(
                uuid=row['id'],
                name=row.get('name') or '',
                latitude=row.get('latitude'),
                longitude=row.get('longitude'),
            )
        return sites

    def _parse_dive_tags(self, conn: sqlite3.Connection) -> dict[str, list[str]]:
        """Parse tag names keyed by dive id"""
        tags = defaultdict(list)
        query = ('SELECT dive_tags.dive_id, tags.name FROM dive_tags '
                 'JOIN tags ON tags.id = dive_tags.tag_id ORDER BY tags.name')
        for dive_id, name in conn.execute(query):
            tags[dive_id].append(name)
        return tags

    def _parse_dives(self, conn: sqlite3.Connection, sites: dict[str, DiveSite],
                     tags: dict[str, list[str]]) -> list[Dive]:
        """Parse dives and link them to sites and tags"""
        dives = []
        diver_ids = set()
        for row in conn.execute('SELECT * FROM dives'):
            row = dict(row)
            if row.get('is_planned'):
                continue
            dive = self._parse_single_dive(row, sites, tags)
            if dive:
                dives.append(dive)
                diver_ids.add(row.get('diver_id'))

        if len(diver_ids) > 1:
            logger.warning(f"Submersion database contains dives from {len(diver_ids)} "
                           "divers; dives from all of them will be used for matching")

        return dives

    def _parse_single_dive(self, row: dict, sites: dict[str, DiveSite],
                           tags: dict[str, list[str]]) -> Dive | None:
        """Build a Dive from a dives row"""
        start_ms = row.get('entry_time') or row.get('dive_date_time')
        if not start_ms:
            return None

        dive_datetime = self._from_wall_clock_millis(start_ms)
        number = row.get('dive_number') or 0

        site = sites.get(row.get('site_id'))
        if not site:
            site = DiveSite(uuid=row.get('site_id') or f"unknown_{number}",
                            name=f"Unknown Site {number}")

        return Dive(
            number=number,
            date=dive_datetime,
            time=dive_datetime,
            duration_minutes=self._duration_minutes(row),
            site=site,
            tags=tags.get(row['id'], []),
        )

    @staticmethod
    def _from_wall_clock_millis(millis: int) -> datetime:
        """Decode a wall-clock-as-UTC epoch millisecond value"""
        return datetime.fromtimestamp(millis / 1000, tz=timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _duration_minutes(row: dict) -> int:
        """Dive duration in whole minutes from runtime, entry/exit or bottom time"""
        if row.get('runtime'):
            return row['runtime'] // 60
        if row.get('entry_time') and row.get('exit_time'):
            return max(0, (row['exit_time'] - row['entry_time']) // 60000)
        if row.get('bottom_time'):
            return row['bottom_time'] // 60
        return 0
