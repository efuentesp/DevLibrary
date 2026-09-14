<!-- SPDX-FileCopyrightText: 2026 DevLibrary Contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Server operations

## Contents

- Service lifecycle
- Upgrade and rollback
- PostgreSQL migration
- ClickHouse telemetry migration
- Safety checks

Local server commands use shell, filesystem, Docker, and database authority. API roles do not constrain that local authority.

## Service lifecycle

```bash
dev-library server status --output json
dev-library server start --background --output json
dev-library server restart --background --output json
dev-library server logs api --lines 100 --output json
dev-library server stop --output json
```

JSON start and restart require background mode. Verify final service status rather than trusting the launch response alone.

## Upgrade and rollback

Read current and available versions first:

```bash
dev-library server versions --output json
dev-library server upgrade --dry-run --output json
```

Execute only the requested direction:

```bash
dev-library server upgrade --version VERSION --force --output json
dev-library server rollback --force --output json
```

Rollback restores PostgreSQL and managed Docker image state, not ClickHouse telemetry. Verify service status and version after completion.

## PostgreSQL migration

Export, validate, then import:

```bash
dev-library server migrate export --file registry.tar.gz --output json
dev-library server migrate validate --archive registry.tar.gz --output json
dev-library server migrate import --archive registry.tar.gz --output json
```

Source commands read `DATABASE_URL`; target commands read `TARGET_DATABASE_URL`. Keep URLs out of output and logs. Never replace these commands with hand-written SQL.

## ClickHouse telemetry migration

```bash
dev-library server migrate export-telemetry --manifest registry.manifest.json --output-dir telemetry-export --output json
dev-library server migrate validate-telemetry --input-dir telemetry-export --output json
dev-library server migrate import-telemetry --input-dir telemetry-export --output json
```

Source commands read `CLICKHOUSE_URL`; target commands read `TARGET_CLICKHOUSE_URL`. Export requires a new destination directory. Validate files and Registry references before import.

## Safety checks

- Confirm source, destination, and backup location before import, upgrade, rollback, or reset.
- Use dry run when available.
- Stop after validation failure. Do not import a damaged archive.
- Report counts, versions, warnings, and final service health.
- Never expose database URLs, generated secrets, archive contents, or customer rows.
