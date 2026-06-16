from __future__ import annotations

import unittest

from pr_atlas_mvp.postgres.connection import normalize_database_url


class PostgresConnectionTests(unittest.TestCase):
    def test_plain_postgresql_url_uses_psycopg_driver(self) -> None:
        self.assertEqual(
            normalize_database_url("postgresql://user:pass@localhost/db"),
            "postgresql+psycopg://user:pass@localhost/db",
        )

    def test_explicit_driver_url_is_preserved(self) -> None:
        self.assertEqual(
            normalize_database_url("postgresql+psycopg://user:pass@localhost/db"),
            "postgresql+psycopg://user:pass@localhost/db",
        )


if __name__ == "__main__":
    unittest.main()
