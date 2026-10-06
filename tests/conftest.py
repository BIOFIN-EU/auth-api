"""
Run against a throwaway database, never the real one, e.g.:

    docker exec auth-db sh -c 'createdb -U "$POSTGRES_USER" auth_pytest_tmp'
    docker run --rm --network biofin_network --env-file .env.dev \
        -e POSTGRES_DB=auth_pytest_tmp -v "$PWD":/usr/src/application auth-api:1.0.0 \
        sh -c "pip install -q pytest httpx && python -m pytest -q tests"
    docker exec auth-db sh -c 'dropdb -U "$POSTGRES_USER" auth_pytest_tmp'

The migration test also needs auth_migrate_tmp (created and dropped the
same way).
"""
import os

import pytest

if not os.environ.get("POSTGRES_DB", "").endswith("_tmp"):
    pytest.exit("Tests only run against a throwaway database (POSTGRES_DB ending in _tmp)", returncode=2)
