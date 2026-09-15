-- SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
-- SPDX-License-Identifier: Apache-2.0

-- Sandbox execution telemetry: one row per dev-library-sandbox-run invocation.
-- Written by POST /api/v1/ingest/sandbox-exec; the CLI spools locally and
-- retries on the next execution when the server is unreachable.

CREATE TABLE IF NOT EXISTS sandbox_exec_events (
    event_id       UUID,
    user_id        String,
    harness        LowCardinality(String) DEFAULT '',
    sandbox_id     String,
    agent_id       Nullable(String),
    session_id     Nullable(String),
    runtime_type   LowCardinality(String) DEFAULT 'docker',
    image          String,
    command        String DEFAULT '' CODEC(ZSTD(1)),
    exit_code      Int32 DEFAULT 0,
    oom_killed     UInt8 DEFAULT 0,
    timed_out      UInt8 DEFAULT 0,
    status         LowCardinality(String) DEFAULT 'success',
    latency_ms     UInt32 DEFAULT 0,
    container_id   Nullable(String),
    output_preview String DEFAULT '' CODEC(ZSTD(3)),
    start_time     DateTime64(3, 'UTC'),
    end_time       DateTime64(3, 'UTC'),
    ingested_at    DateTime64(3, 'UTC') DEFAULT now64(3),
    INDEX idx_see_user_id user_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_see_sandbox_id sandbox_id TYPE bloom_filter(0.01) GRANULARITY 1
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(start_time)
ORDER BY (user_id, sandbox_id, start_time);
