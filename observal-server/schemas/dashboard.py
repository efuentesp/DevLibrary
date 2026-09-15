# SPDX-FileCopyrightText: 2026 Subramania Raja <dhanpraja231@gmail.com>
# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-FileCopyrightText: 2026 Kaushik Kumar <kaushikrjpm10@gmail.com>
# SPDX-FileCopyrightText: 2026 Lokesh Selvam <lokeshselvam7025@gmail.com>
# SPDX-FileCopyrightText: 2026 Swathi Saravanan <ss4522@cornell.edu>
# SPDX-License-Identifier: Apache-2.0

import uuid

from pydantic import BaseModel


class TimeSeriesPoint(BaseModel):
    date: str
    value: int


class OverviewStats(BaseModel):
    total_mcps: int
    total_agents: int
    total_users: int
    total_tool_calls: int
    total_agent_interactions: int


class TopItem(BaseModel):
    id: uuid.UUID
    name: str
    value: float


class TopAgentItem(BaseModel):
    id: uuid.UUID
    name: str
    namespace: str = ""
    slug: str = ""
    qualified_name: str = ""
    description: str = ""
    owner: str = ""
    created_by_username: str | None = None
    version: str = ""
    download_count: int = 0
    average_rating: float | None = None


class LeaderboardItem(TopAgentItem):
    """Same as TopAgentItem - used by the leaderboard endpoint."""

    created_by_email: str = ""
    created_by_username: str | None = None


class ComponentLeaderboardItem(BaseModel):
    id: uuid.UUID
    name: str
    namespace: str = ""
    slug: str = ""
    qualified_name: str = ""
    component_type: str
    description: str = ""
    download_count: int = 0
    created_by_email: str = ""
    average_rating: float | None = None
    total_reviews: int = 0


class TrendPoint(BaseModel):
    date: str
    submissions: int
    users: int


# --- Token usage ---


class TokenByEntity(BaseModel):
    id: str
    name: str
    input: int
    output: int
    total: int
    traces: int


class TokenTimePoint(BaseModel):
    date: str
    input: int
    output: int


class TokenStats(BaseModel):
    total_input: int
    total_output: int
    total_tokens: int
    avg_per_trace: float
    by_agent: list[TokenByEntity]
    by_mcp: list[TokenByEntity]
    over_time: list[TokenTimePoint]


# --- harness usage ---


class HarnessBreakdown(BaseModel):
    harness: str
    traces: int
    avg_latency_ms: float
    error_count: int
    error_rate: float


class HarnessUsage(BaseModel):
    harnesses: list[HarnessBreakdown]


# --- Sandbox metrics ---


class SandboxRun(BaseModel):
    """One sandbox execution outcome from sandbox_exec_events."""

    event_id: str
    sandbox_id: str
    image: str
    runtime_type: str
    command: str
    status: str
    exit_code: int
    oom_killed: bool
    timed_out: bool
    latency_ms: int
    harness: str
    agent_id: str | None = None
    start_time: str
    output_preview: str = ""


class SandboxTrendPoint(BaseModel):
    date: str
    runs: int
    failures: int


class SandboxTopItem(BaseModel):
    sandbox_id: str
    image: str
    runs: int
    failure_rate: float
    avg_latency_ms: float


class SandboxStats(BaseModel):
    total_runs: int
    success_count: int
    error_count: int
    timeout_count: int
    timeout_rate: float
    oom_count: int
    oom_rate: float
    avg_latency_ms: float | None
    p95_latency_ms: float | None
    runs_over_time: list[SandboxTrendPoint]
    top_sandboxes: list[SandboxTopItem]
    recent_failures: list[SandboxRun]


# --- GraphRAG metrics ---


class RelevanceBucket(BaseModel):
    bucket: str
    count: int


class GraphRagQuery(BaseModel):
    span_id: str
    name: str
    query_interface: str | None
    entities: int | None
    relationships: int | None
    relevance_score: float | None
    latency_ms: int | None
    timestamp: str


class GraphRagStats(BaseModel):
    total_queries: int
    avg_entities: float | None
    avg_relationships: float | None
    avg_relevance_score: float | None
    avg_embedding_latency_ms: float | None
    relevance_distribution: list[RelevanceBucket]
    recent_queries: list[GraphRagQuery]


# --- Latency heatmap ---


class LatencyCell(BaseModel):
    name: str
    hour: str
    p50: float
    p90: float
    p99: float


# --- Unannotated traces ---


class UnannotatedTrace(BaseModel):
    trace_id: str
    name: str | None
    session_id: str | None
    harness: str | None
    trace_type: str | None
    start_time: str
