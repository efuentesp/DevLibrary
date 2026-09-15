<!-- SPDX-FileCopyrightText: 2026 Apoorv Garg <apoorvgarg.21@gmail.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# `dev-library config`

Manage local CLI configuration. Configuration lives in `~/.observal/config.json`; aliases live in `~/.observal/aliases.json`. Both files are written atomically with mode `0600`.

## Commands

| Command | Description |
| --- | --- |
| `dev-library config show` | Show effective configuration without exposing credentials |
| `dev-library config set` | Set a validated user-managed value |
| `dev-library config path` | Print the configuration file path |
| `dev-library config alias` | Set or remove a local reference alias |
| `dev-library config aliases` | List local aliases |

Every command supports explicit table and JSON output. Human-readable table output is the default. `config path` preserves a bare path in table mode for shell composition.

## Show configuration

```bash
dev-library config show
dev-library config show --output json
```

Token values and fragments are never displayed. Output reports only whether access, refresh, or harness-hook credentials are configured. Environment overrides are included because the command shows effective configuration.

## Set configuration

```bash
dev-library config set server_url https://observal.example.com
dev-library config set timeout 60 --output json
dev-library config set update_check false
dev-library config set update_check_interval 86400
dev-library config set update_check_repo Observal/Observal
```

Only these user-managed keys are accepted:

| Key | Accepted value |
| --- | --- |
| `server_url` | HTTP or HTTPS URL without embedded credentials |
| `timeout` | Positive integer seconds |
| `update_check` | `true`, `false`, `yes`, `no`, `on`, `off`, `1`, or `0` |
| `update_check_interval` | Integer seconds, minimum 60 |
| `update_check_repo` | `owner/repository` or an empty string |

Authentication and identity fields are managed by `dev-library auth` and cannot be set here. The removed `output` and `color` settings had no runtime consumers. Select JSON explicitly for each command.

JSON output distinguishes the persisted value from the effective value, which may be overridden by an environment variable.

## Configuration path

```bash
dev-library config path
dev-library config path --output json
```

Table mode prints only the absolute path. JSON includes the path and whether the file currently exists.

## Set or remove an alias

```bash
dev-library config alias reviewer alice/reviewer
dev-library config alias reviewer alice/reviewer --output json
dev-library config alias reviewer
```

Alias names must start with a letter and may contain letters, numbers, dots, underscores, and hyphens, up to 64 characters. Targets may be UUIDs, canonical `namespace/slug` identities, names, or other references accepted by the destination command.

Omitting the target removes the alias. Removing an already absent alias is an idempotent success with `changed` set to `false` in JSON.

## List aliases

```bash
dev-library config aliases
dev-library config aliases --output json
```

JSON returns an `items` array and `total`. Empty output preserves the same shape.

## Environment overrides

Environment values take precedence over persisted values for the current invocation. `config set` changes the file but does not replace an active environment override.

See [Environment variables](../reference/environment-variables.md) for supported overrides.

## Related

* [Config files](../reference/config-files.md): local file schemas and permissions
* [`dev-library auth`](auth.md): authentication-managed values
