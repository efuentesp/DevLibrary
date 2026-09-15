# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Adoption counters maintained by record_component_download."""

from __future__ import annotations

import uuid

from models.download import ComponentDownloadRecord
from services.download_tracker import record_component_download


class _ExecResult:
    def __init__(self, first_value):
        self._first = first_value

    def first(self):
        return self._first


class FakeVersion:
    download_count: int = 0


class FakeListing:
    def __init__(self):
        self.unique_agents = 0
        self.latest_version = FakeVersion()


class FakeDB:
    """AsyncSession double: canned execute() results, recorded adds."""

    def __init__(self, prior_pull_seen: bool, listing):
        self._exec_results = [_ExecResult("prior-row" if prior_pull_seen else None)]
        self.listing = listing
        self.added: list = []

    async def execute(self, *_args, **_kwargs):
        if self._exec_results:
            return self._exec_results.pop(0)
        return _ExecResult(None)

    async def get(self, _model, _pk):
        return self.listing

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None


async def test_first_download_bumps_both_counters():
    listing = FakeListing()
    db = FakeDB(prior_pull_seen=False, listing=listing)
    component_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    await record_component_download("sandbox", component_id, "latest", agent_id, "api", db)

    assert len(db.added) == 1
    record = db.added[0]
    assert isinstance(record, ComponentDownloadRecord)
    assert record.component_type == "sandbox"
    assert record.component_id == component_id
    assert record.agent_id == agent_id
    assert record.version_ref == "latest"
    assert listing.latest_version.download_count == 1
    assert listing.unique_agents == 1


async def test_repeat_pull_same_agent_only_bumps_download_count():
    listing = FakeListing()
    listing.latest_version.download_count = 1
    listing.unique_agents = 1
    db = FakeDB(prior_pull_seen=True, listing=listing)

    await record_component_download("sandbox", uuid.uuid4(), "latest", uuid.uuid4(), "api", db)

    assert len(db.added) == 1  # every pull still records a row
    assert listing.latest_version.download_count == 2
    assert listing.unique_agents == 1  # unchanged


async def test_unknown_component_type_records_row_without_counters():
    listing = FakeListing()
    db = FakeDB(prior_pull_seen=False, listing=listing)

    await record_component_download("component-type-of-the-future", uuid.uuid4(), "latest", uuid.uuid4(), "api", db)

    assert len(db.added) == 1
    assert listing.latest_version.download_count == 0
    assert listing.unique_agents == 0


async def test_missing_listing_records_row_without_counters():
    db = FakeDB(prior_pull_seen=False, listing=None)

    await record_component_download("sandbox", uuid.uuid4(), "latest", uuid.uuid4(), "api", db)

    assert len(db.added) == 1
