<!-- SPDX-FileCopyrightText: 2026 DevLibrary Contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Governance and identity

## Contents

- Settings and diagnostics
- Users
- Review queue
- Security and audit
- SAML and SCIM

## Settings and diagnostics

```bash
dev-library admin settings --output json
dev-library admin set KEY VALUE --output json
dev-library admin diagnostics --output json
dev-library admin trace-privacy --output json
dev-library admin trace-privacy-set true --output json
dev-library admin cache-clear --output json
```

Read current settings before mutation. The server redacts sensitive values, and update output must not echo supplied secrets.

## Users

```bash
dev-library admin users --output json
dev-library admin create-user user@example.com 'Example User' --role user --output json
dev-library admin reset-password user@example.com --generate --output json
dev-library admin set-role user@example.com admin --output json
dev-library admin delete-user user@example.com --force --output json
```

Valid roles are `super_admin`, `admin`, `reviewer`, and `user`. Creation and reset can return a one-time password. Treat the entire response as secret and disclose it only to the intended user when explicitly requested. Verify role changes with the user list.

## Review queue

List and select by UUID:

```bash
dev-library admin review list --output json
dev-library admin review list --type mcp --output json
dev-library admin review list --tab agents --output json
dev-library admin review list --team-id TEAM_UUID --output json
dev-library admin review show REVIEW_UUID --output json
```

Review only the requested item after inspecting details:

```bash
dev-library admin review approve REVIEW_UUID --output json
dev-library admin review approve AGENT_UUID --agent --output json
dev-library admin review approve BUNDLE_UUID --bundle --output json
dev-library admin review reject REVIEW_UUID --reason 'Not reproducible' --output json
```

Component types include `mcp`, `skill`, `hook`, `prompt`, and `sandbox`. Agent and bundle selectors are mutually exclusive. Verify returned status and do not act on unrelated queue items.

## Security and audit

```bash
dev-library admin security-events --limit 50 --offset 0 --output json
dev-library admin audit-log --limit 100 --offset 0 --output json
dev-library admin audit-log --actor user@example.com --source server --output json
dev-library admin audit-log-export --file audit.json --output json
```

Use the narrowest filters that answer the investigation. Treat event details as sensitive. Export destinations must be explicit, and overwriting an existing file requires the documented force flag.

## SAML and SCIM

```bash
dev-library admin saml-config --output json
dev-library admin saml-config-set --idp-entity-id ID --idp-sso-url URL --idp-x509-cert "$(cat idp-cert.pem)" --active --output json
dev-library admin saml-config-delete --force --output json
dev-library admin scim-tokens --output json
dev-library admin scim-token-create --description 'Okta' --output json
dev-library admin scim-token-revoke TOKEN_UUID --force --output json
```

Every SAML update requires entity ID, SSO URL, and certificate. SCIM creation returns a bearer token once. Do not repeat it after initial delivery. Verify active SAML state and SCIM token metadata without exposing secrets.
