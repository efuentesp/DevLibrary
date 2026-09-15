// SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
// SPDX-License-Identifier: Apache-2.0

import {
	AreaChart,
	Area,
	XAxis,
	YAxis,
	CartesianGrid,
	Tooltip,
	ResponsiveContainer,
	Line,
} from "recharts";
import { useSandboxMetrics } from "@/hooks/use-dashboard-api";
import { StatCard } from "./stat-card";

function pct(rate: number): string {
	return `${(rate * 100).toFixed(1)}%`;
}

function ms(latency: number | null | undefined): string {
	if (latency == null) return "—";
	return latency >= 1000
		? `${(latency / 1000).toFixed(1)}s`
		: `${Math.round(latency)}ms`;
}

export function SandboxTab({ range = "30d" }: { range?: string }) {
	const { data, isLoading, isError } = useSandboxMetrics(range);

	if (isError) {
		return (
			<div className="flex flex-col items-center justify-center py-16 text-center">
				<p className="text-sm text-muted-foreground">
					Failed to load sandbox telemetry. Check your connection and try again.
				</p>
			</div>
		);
	}

	if (isLoading) {
		return (
			<div className="space-y-6 pt-4">
				<div className="h-32 rounded-xl bg-card shadow-sm animate-pulse" />
				<div className="h-80 rounded-xl bg-card shadow-sm animate-pulse" />
			</div>
		);
	}

	const successRate = data?.total_runs
		? data.success_count / data.total_runs
		: 0;
	const chartData = (data?.runs_over_time ?? []).map((point) => ({
		date: point.date.slice(5),
		runs: point.runs,
		failures: point.failures,
	}));

	return (
		<div className="space-y-6 pt-4">
			<div className="grid grid-cols-4 gap-4">
				<StatCard
					label="Total runs"
					value={data?.total_runs ?? 0}
					subtitle={`${pct(successRate)} success`}
				/>
				<StatCard
					label="Timeouts"
					value={data?.timeout_count ?? 0}
					subtitle={data?.total_runs ? pct(data.timeout_rate) : "—"}
				/>
				<StatCard
					label="OOM kills"
					value={data?.oom_count ?? 0}
					subtitle={data?.total_runs ? pct(data.oom_rate) : "—"}
				/>
				<StatCard
					label="p95 latency"
					value={ms(data?.p95_latency_ms)}
					subtitle={`avg ${ms(data?.avg_latency_ms)}`}
				/>
			</div>

			{chartData.length > 0 && (
				<div className="rounded-xl bg-card p-4 shadow-sm">
					<h3 className="mb-4 text-sm font-medium">Executions over time</h3>
					<div className="h-72">
						<ResponsiveContainer width="100%" height="100%">
							<AreaChart data={chartData}>
								<defs>
									<linearGradient id="sandboxRuns" x1="0" y1="0" x2="0" y2="1">
										<stop
											offset="5%"
											stopColor="oklch(var(--primary))"
											stopOpacity={0.3}
										/>
										<stop
											offset="95%"
											stopColor="oklch(var(--primary))"
											stopOpacity={0}
										/>
									</linearGradient>
								</defs>
								<CartesianGrid strokeDasharray="3 3" stroke="oklch(var(--border))" />
								<XAxis
									dataKey="date"
									stroke="oklch(var(--muted-foreground))"
									fontSize={12}
								/>
								<YAxis
									stroke="oklch(var(--muted-foreground))"
									fontSize={12}
									allowDecimals={false}
								/>
								<Tooltip
									contentStyle={{
										background: "oklch(var(--popover))",
										border: "1px solid oklch(var(--border))",
										borderRadius: "8px",
										color: "oklch(var(--popover-foreground))",
									}}
								/>
								<Area
									type="monotone"
									dataKey="runs"
									stroke="oklch(var(--primary))"
									fill="url(#sandboxRuns)"
									name="Runs"
								/>
								<Line
									type="monotone"
									dataKey="failures"
									stroke="oklch(var(--destructive))"
									strokeWidth={2}
									dot={false}
									name="Failures"
								/>
							</AreaChart>
						</ResponsiveContainer>
					</div>
				</div>
			)}

			<div className="grid grid-cols-2 gap-4">
				<div className="rounded-xl bg-card p-4 shadow-sm">
					<h3 className="mb-3 text-sm font-medium">Top sandboxes</h3>
					{(data?.top_sandboxes ?? []).length === 0 ? (
						<p className="py-8 text-center text-sm text-muted-foreground">
							No sandbox executions yet
						</p>
					) : (
						<table className="w-full text-sm">
							<thead>
								<tr className="border-b border-border text-left text-xs text-muted-foreground">
									<th className="pb-2 font-medium">Sandbox</th>
									<th className="pb-2 text-right font-medium">Runs</th>
									<th className="pb-2 text-right font-medium">Fail rate</th>
									<th className="pb-2 text-right font-medium">Avg</th>
								</tr>
							</thead>
							<tbody>
								{(data?.top_sandboxes ?? []).map((item) => (
									<tr
										key={item.sandbox_id}
										className="border-b border-border/50 last:border-0"
									>
										<td className="py-2">
											<div className="font-medium">{item.sandbox_id}</div>
											<div className="text-xs text-muted-foreground">{item.image}</div>
										</td>
										<td className="py-2 text-right tabular-nums">{item.runs}</td>
										<td className="py-2 text-right tabular-nums">
											<span
												className={
													item.failure_rate > 0.2
														? "text-destructive"
														: "text-muted-foreground"
												}
											>
												{pct(item.failure_rate)}
											</span>
										</td>
										<td className="py-2 text-right tabular-nums text-muted-foreground">
											{ms(item.avg_latency_ms)}
										</td>
									</tr>
								))}
							</tbody>
						</table>
					)}
				</div>

				<div className="rounded-xl bg-card p-4 shadow-sm">
					<h3 className="mb-3 text-sm font-medium">Recent failures</h3>
					{(data?.recent_failures ?? []).length === 0 ? (
						<p className="py-8 text-center text-sm text-muted-foreground">
							No failures — everything green
						</p>
					) : (
						<div className="max-h-80 space-y-2 overflow-y-auto">
							{(data?.recent_failures ?? []).map((run) => (
								<details
									key={run.event_id}
									className="rounded-lg border border-border/50 px-3 py-2 text-sm"
								>
									<summary className="cursor-pointer list-none">
										<span
											className={
												run.timed_out || run.oom_killed
													? "font-medium text-warning"
													: "font-medium text-destructive"
											}
										>
											{run.status}
										</span>
										{run.timed_out && (
											<span className="ml-2 rounded bg-warning/15 px-1.5 py-0.5 text-xs text-warning">
												timeout
											</span>
										)}
										{run.oom_killed && (
											<span className="ml-2 rounded bg-warning/15 px-1.5 py-0.5 text-xs text-warning">
												oom
											</span>
										)}
										<span className="ml-2 text-muted-foreground">
											{run.sandbox_id} · exit {run.exit_code} · {ms(run.latency_ms)} ·{" "}
											{run.start_time.slice(0, 19)}
										</span>
									</summary>
									<div className="mt-2 space-y-1">
										<div className="truncate font-mono text-xs text-muted-foreground">
											$ {run.command || "(entrypoint)"}
										</div>
										{run.output_preview && (
											<pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded bg-muted p-2 font-mono text-xs">
												{run.output_preview}
											</pre>
										)}
									</div>
								</details>
							))}
						</div>
					)}
				</div>
			</div>
		</div>
	);
}
