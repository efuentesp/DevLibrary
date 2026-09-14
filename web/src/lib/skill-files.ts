// SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
// SPDX-License-Identifier: Apache-2.0

/**
 * Multi-file skill (extra_files) contract for the web frontend.
 *
 * Mirrors observal_shared.skill_files on the server and dev_library_cli.skill_bundle
 * on the CLI: relative POSIX paths, traversal-free, no nested SKILL.md, no .git,
 * case-insensitive unique paths, no collision with the legacy script slot, and
 * count/size caps. Keep the three implementations in sync when the contract changes.
 */

export interface SkillExtraFile {
	path: string;
	content: string;
	encoding: "utf-8" | "base64";
}

export const MAX_EXTRA_FILES = 100;
export const MAX_EXTRA_FILE_BYTES = 2 * 1024 * 1024; // 2 MB decoded per file
export const MAX_EXTRA_TOTAL_BYTES = 8 * 1024 * 1024; // 8 MB decoded total
const MAX_EXTRA_PATH_LENGTH = 200;
const MAX_EXTRA_PATH_DEPTH = 10;

const RESERVED_FIRST_SEGMENTS = new Set([".git"]);
const SKILL_MD = "skill.md";

export class SkillExtraFileError extends Error {}

/** Validate and normalize one extra-file path; throws SkillExtraFileError. */
export function validateSkillExtraFilePath(path: string): string {
	const candidate = path.trim();
	if (!candidate) throw new SkillExtraFileError("Path cannot be empty");
	if (candidate.length > MAX_EXTRA_PATH_LENGTH)
		throw new SkillExtraFileError(
			`Path exceeds ${MAX_EXTRA_PATH_LENGTH} characters`,
		);
	if (candidate.includes("\\"))
		throw new SkillExtraFileError("Path must use forward slashes only");
	if (candidate.includes(":"))
		throw new SkillExtraFileError("Path must not contain ':'");
	if (/[^\x20-\x7E]/.test(candidate))
		throw new SkillExtraFileError(
			"Path must not contain control or non-ASCII characters",
		);
	if (candidate.startsWith("/"))
		throw new SkillExtraFileError("Path must be relative to the skill directory");
	const parts = candidate.split("/").filter((p) => p.length > 0);
	if (parts.length === 0) throw new SkillExtraFileError("Path cannot be empty");
	if (parts.length > MAX_EXTRA_PATH_DEPTH)
		throw new SkillExtraFileError(
			`Path exceeds ${MAX_EXTRA_PATH_DEPTH} segments`,
		);
	for (const part of parts) {
		if (part === "." || part === "..")
			throw new SkillExtraFileError("Path must not traverse directories");
	}
	if (parts[0] && RESERVED_FIRST_SEGMENTS.has(parts[0]))
		throw new SkillExtraFileError("Path must not start with .git");
	if (parts[parts.length - 1].toLowerCase() === SKILL_MD)
		throw new SkillExtraFileError(
			"Paths must not end in SKILL.md (harness scanners treat it as a skill root)",
		);
	return parts.join("/");
}

/** Decoded byte size of one entry's content. */
export function skillExtraFileBytes(entry: SkillExtraFile): number {
	if (entry.encoding === "base64") {
		const clean = entry.content.replace(/\s+/g, "");
		return (
			Math.floor((clean.length * 3) / 4) -
			(clean.endsWith("==") ? 2 : clean.endsWith("=") ? 1 : 0)
		);
	}
	return new TextEncoder().encode(entry.content).length;
}

/**
 * Validate a full extra_files list and return normalized entries.
 * Throws SkillExtraFileError on any contract violation.
 */
export function validateSkillExtraFiles(
	entries: SkillExtraFile[],
	scriptFilename?: string | null,
): SkillExtraFile[] {
	if (entries.length > MAX_EXTRA_FILES)
		throw new SkillExtraFileError(
			`Too many files: maximum is ${MAX_EXTRA_FILES}`,
		);
	const seen = new Set<string>();
	let total = 0;
	for (const entry of entries) {
		entry.path = validateSkillExtraFilePath(entry.path);
		const key = entry.path.toLowerCase();
		if (seen.has(key))
			throw new SkillExtraFileError(
				`Duplicate path (paths compare case-insensitively): ${entry.path}`,
			);
		seen.add(key);
		if (scriptFilename && key === `scripts/${scriptFilename.toLowerCase()}`)
			throw new SkillExtraFileError(
				`${entry.path} collides with the script slot; use a different path`,
			);
		const size = skillExtraFileBytes(entry);
		if (size > MAX_EXTRA_FILE_BYTES)
			throw new SkillExtraFileError(
				`${entry.path} exceeds ${MAX_EXTRA_FILE_BYTES} decoded bytes`,
			);
		total += size;
	}
	if (total > MAX_EXTRA_TOTAL_BYTES)
		throw new SkillExtraFileError(
			`Extra files total exceeds ${MAX_EXTRA_TOTAL_BYTES} decoded bytes`,
		);
	return entries;
}

/**
 * Read a browser File into an extra-file entry: UTF-8 when it decodes cleanly
 * (fatal TextDecoder probe, matching the CLI), base64 otherwise.
 */
export async function fileToSkillExtraEntry(
	file: File,
): Promise<SkillExtraFile> {
	const buffer = await file.arrayBuffer();
	try {
		const text = new TextDecoder("utf-8", { fatal: true }).decode(buffer);
		return { path: file.name, content: text, encoding: "utf-8" };
	} catch {
		let binary = "";
		const bytes = new Uint8Array(buffer);
		const chunk = 0x8000;
		for (let i = 0; i < bytes.length; i += chunk) {
			binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
		}
		return { path: file.name, content: btoa(binary), encoding: "base64" };
	}
}
