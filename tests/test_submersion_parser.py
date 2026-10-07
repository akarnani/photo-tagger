"""Tests for submersion_parser module"""

import logging
import sqlite3
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner

from photo_tagger.cli import main
from photo_tagger.submersion_parser import SubmersionParser, is_sqlite_file

# Subset of Submersion's schema covering the columns photo-tagger reads
SCHEMA = """
CREATE TABLE dive_sites (
    id TEXT NOT NULL PRIMARY KEY,
    diver_id TEXT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    latitude REAL NULL,
    longitude REAL NULL
);
CREATE TABLE dives (
    id TEXT NOT NULL PRIMARY KEY,
    diver_id TEXT NULL,
    dive_number INTEGER NULL,
    dive_date_time INTEGER NOT NULL,
    entry_time INTEGER NULL,
    exit_time INTEGER NULL,
    bottom_time INTEGER NULL,
    runtime INTEGER NULL,
    notes TEXT NOT NULL DEFAULT '',
    site_id TEXT NULL REFERENCES dive_sites (id),
    is_planned INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE tags (
    id TEXT NOT NULL PRIMARY KEY,
    diver_id TEXT NULL,
    name TEXT NOT NULL
);
CREATE TABLE dive_tags (
    id TEXT NOT NULL PRIMARY KEY,
    dive_id TEXT NOT NULL REFERENCES dives (id),
    tag_id TEXT NOT NULL REFERENCES tags (id),
    created_at INTEGER NOT NULL
);
"""


def wall_clock_millis(dt: datetime) -> int:
    """Encode a wall-clock datetime the way Submersion stores it"""
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


def insert_dive(conn, dive_id, start=datetime(2026, 6, 19, 16, 16), dive_number=1,
                site_id='site1', diver_id='diver1', is_planned=0, use_entry_time=True,
                runtime=3840, exit_offset_s=3840, bottom_time=3660):
    start_ms = wall_clock_millis(start)
    entry = start_ms if use_entry_time else None
    exit_time = start_ms + exit_offset_s * 1000 if exit_offset_s is not None else None
    conn.execute(
        'INSERT INTO dives (id, diver_id, dive_number, dive_date_time, entry_time, exit_time, '
        'bottom_time, runtime, site_id, is_planned) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (dive_id, diver_id, dive_number, start_ms, entry, exit_time, bottom_time, runtime,
         site_id, is_planned))


@pytest.fixture
def db_path(tmp_path):
    """Submersion database with one site, one dive and two tags"""
    path = tmp_path / 'submersion.db'
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO dive_sites (id, name, latitude, longitude) "
                 "VALUES ('site1', 'Blue Hole', 17.316, -87.535)")
    conn.execute("INSERT INTO tags (id, name) VALUES ('t1', 'camera'), ('t2', 'boat')")
    insert_dive(conn, 'dive1', dive_number=530)
    conn.execute("INSERT INTO dive_tags (id, dive_id, tag_id, created_at) "
                 "VALUES ('dt1', 'dive1', 't1', 0), ('dt2', 'dive1', 't2', 0)")
    conn.commit()
    conn.close()
    return path


def add_rows(path, *dives, **kwargs):
    conn = sqlite3.connect(path)
    for dive_id in dives:
        insert_dive(conn, dive_id, **kwargs)
    conn.commit()
    conn.close()


class TestSubmersionParser:

    def test_parse_simple_dive(self, db_path):
        """Dive time, duration, site and tags are read from the database"""
        dives = SubmersionParser(str(db_path)).parse()

        assert len(dives) == 1
        dive = dives[0]
        assert dive.number == 530
        assert dive.time == datetime(2026, 6, 19, 16, 16)
        assert dive.date == dive.time
        assert dive.time.tzinfo is None
        assert dive.duration_minutes == 64
        assert dive.site.name == 'Blue Hole'
        assert dive.site.latitude == 17.316
        assert dive.site.longitude == -87.535
        assert dive.tags == ['boat', 'camera']

    def test_falls_back_to_dive_date_time(self, db_path):
        """dive_date_time is used when entry_time is missing"""
        conn = sqlite3.connect(db_path)
        conn.execute('DELETE FROM dives')
        insert_dive(conn, 'dive1', start=datetime(2024, 1, 15, 10, 30), use_entry_time=False)
        conn.commit()
        conn.close()

        dive = SubmersionParser(str(db_path)).parse()[0]
        assert dive.time == datetime(2024, 1, 15, 10, 30)

    @pytest.mark.parametrize('runtime, exit_offset_s, bottom_time, expected', [
        (3840, 4000, 3000, 64),     # runtime wins
        (None, 3000, 2000, 50),     # exit - entry
        (None, None, 2700, 45),     # bottom time
        (None, None, None, 0),      # nothing recorded
    ])
    def test_duration_fallbacks(self, tmp_path, runtime, exit_offset_s, bottom_time, expected):
        """Duration uses runtime, then exit - entry, then bottom time"""
        path = tmp_path / 'submersion.db'
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA)
        insert_dive(conn, 'dive1', runtime=runtime, exit_offset_s=exit_offset_s,
                    bottom_time=bottom_time)
        conn.commit()
        conn.close()

        assert SubmersionParser(str(path)).parse()[0].duration_minutes == expected

    def test_planned_dives_skipped(self, db_path):
        """Dives from the planner are not logged dives"""
        add_rows(db_path, 'planned', is_planned=1, dive_number=None)

        dives = SubmersionParser(str(db_path)).parse()
        assert [d.number for d in dives] == [530]

    def test_missing_dive_number(self, db_path):
        """A dive without a number is reported as dive 0"""
        add_rows(db_path, 'dive2', dive_number=None)

        dives = SubmersionParser(str(db_path)).parse()
        assert sorted(d.number for d in dives) == [0, 530]

    def test_missing_site(self, db_path):
        """A dive with no site gets a placeholder site without GPS"""
        add_rows(db_path, 'dive2', dive_number=7, site_id=None)

        dive = next(d for d in SubmersionParser(str(db_path)).parse() if d.number == 7)
        assert dive.site.name == 'Unknown Site 7'
        assert dive.site.latitude is None
        assert dive.tags == []

    def test_site_without_gps(self, db_path):
        """Sites without coordinates have None latitude and longitude"""
        conn = sqlite3.connect(db_path)
        conn.execute('UPDATE dive_sites SET latitude = NULL, longitude = NULL')
        conn.commit()
        conn.close()

        site = SubmersionParser(str(db_path)).parse()[0].site
        assert site.latitude is None
        assert site.longitude is None

    def test_multiple_divers_warns(self, db_path, caplog):
        """Dives from more than one diver are all used, with a warning"""
        add_rows(db_path, 'dive2', diver_id='diver2')

        with caplog.at_level(logging.WARNING):
            dives = SubmersionParser(str(db_path)).parse()

        assert len(dives) == 2
        assert '2 divers' in caplog.text

    def test_reads_uncheckpointed_wal(self, db_path):
        """Changes still in the -wal file are visible to the parser"""
        writer = sqlite3.connect(db_path)
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute('PRAGMA wal_autocheckpoint=0')
        insert_dive(writer, 'dive2', dive_number=531)
        writer.commit()
        try:
            assert (db_path.parent / 'submersion.db-wal').stat().st_size > 0
            dives = SubmersionParser(str(db_path)).parse()
            assert sorted(d.number for d in dives) == [530, 531]
        finally:
            writer.close()

    def test_database_not_modified(self, db_path):
        """The database is opened read-only"""
        before = db_path.read_bytes()
        SubmersionParser(str(db_path)).parse()
        assert db_path.read_bytes() == before

    def test_path_with_special_characters(self, tmp_path, db_path):
        """Paths are URI-escaped when opening read-only"""
        target = tmp_path / 'my dives #1?' / 'submersion.db'
        target.parent.mkdir()
        target.write_bytes(db_path.read_bytes())

        assert len(SubmersionParser(str(target)).parse()) == 1

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SubmersionParser(str(tmp_path / 'missing.db')).parse()

    def test_encrypted_database(self, tmp_path):
        """A file that is not plain SQLite reports the encryption setting"""
        path = tmp_path / 'submersion.db'
        path.write_bytes(b'\x8a\x13' * 2048)

        with pytest.raises(ValueError, match='encryption'):
            SubmersionParser(str(path)).parse()

    def test_is_sqlite_file(self, tmp_path, db_path):
        ssrf = tmp_path / 'log.ssrf'
        ssrf.write_text('<divelog/>')

        assert is_sqlite_file(str(db_path))
        assert not is_sqlite_file(str(ssrf))
        assert not is_sqlite_file(str(tmp_path / 'missing.db'))


class TestCliDiveLogDetection:

    def test_cli_reads_submersion_database(self, db_path, tmp_path):
        """-s accepts a Submersion database and parses it"""
        images = tmp_path / 'images'
        images.mkdir()

        result = CliRunner().invoke(main, ['-s', str(db_path), '-i', str(images), '-v'])

        assert 'Parsing Submersion database' in result.output
        assert 'Found 1 dives' in result.output

    def test_cli_dive_log_option(self, db_path, tmp_path):
        """--dive-log is accepted as the long option name"""
        images = tmp_path / 'images'
        images.mkdir()

        result = CliRunner().invoke(main, ['--dive-log', str(db_path), '-i', str(images), '-v'])

        assert 'Found 1 dives' in result.output
