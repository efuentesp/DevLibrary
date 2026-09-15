// SPDX-FileCopyrightText: 2026 Aryan Iyappan <aryaniyappan2006@gmail.com>
// SPDX-FileCopyrightText: 2026 Harishankar <harishankar0301@gmail.com>
// SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
// SPDX-FileCopyrightText: 2026 Kaushik Kumar <kaushikrjpm10@gmail.com>
// SPDX-FileCopyrightText: 2026 Lokesh Selvam <lokeshselvam7025@gmail.com>
// SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com>
// SPDX-FileCopyrightText: 2026 Swathi Saravanan <ss4522@cornell.edu>
// SPDX-License-Identifier: Apache-2.0

// ── Overview ────────────────────────────────────────────────────────

export interface OverviewStats {
	total_mcps: number;
	total_agents: number;
	total_users: number;
	total_tool_calls: number;
	total_agent_interactions: number;
}

export interface TopItem {
	id: string;
	name: string;
	value: number;
}

export interface TrendPoint {
	date: string;
	submissions: number;
	users: number;
}

// ── Tokens ──────────────────────────────────────────────────────────

export interface TokenStats {
	total_input: number;
	total_output: number;
	total_tokens: number;
	avg_per_trace: number;
	by_agent: TokenUsageRow[];
	by_mcp: TokenUsageRow[];
	over_time: { date: string; input: number; output: number }[];
}

export interface TokenUsageRow {
	name: string;
	input: number;
	output: number;
	total: number;
	traces: number;
}

// ── harness Usage ───────────────────────────────────────────────────────

export interface HarnessRow {
	harness: string;
	traces: number;
	avg_latency_ms: number;
	error_count: number;
	error_rate: number;
}

export interface HarnessUsageData {
	harnesses: HarnessRow[];
}

// ── Sandbox executions ────────────────────────────────────────────────

export interface SandboxRunEvent {
	event_id: string;
	sandbox_id: string;
	image: string;
	runtime_type: string;
	command: string;
	status: string;
	exit_code: number;
	oom_killed: boolean;
	timed_out: boolean;
	latency_ms: number;
	harness: string;
	agent_id?: string | null;
	start_time: string;
	output_preview?: string;
}

export interface SandboxTrendPoint {
	date: string;
	runs: number;
	failures: number;
}

export interface SandboxTopItem {
	sandbox_id: string;
	image: string;
	runs: number;
	failure_rate: number;
	avg_latency_ms: number;
}

export interface SandboxStatsData {
	total_runs: number;
	success_count: number;
	error_count: number;
	timeout_count: number;
	timeout_rate: number;
	oom_count: number;
	oom_rate: number;
	avg_latency_ms?: number | null;
	p95_latency_ms?: number | null;
	runs_over_time: SandboxTrendPoint[];
	top_sandboxes: SandboxTopItem[];
	recent_failures: SandboxRunEvent[];
}
