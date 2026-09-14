<!-- SPDX-FileCopyrightText: 2026 Hemalatha Madeswaran <hemalathamadeswaran@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DevLibrary CLI Command Reference

Auto-generated from the Typer app by `scripts/sync_observal_skill.py`. Do not edit manually.

<!-- BEGIN AUTO-GENERATED COMMAND REFERENCE -->
Every command available in the installed CLI. This block is generated from the Typer app by `scripts/sync_observal_skill.py`. If a flag you need is missing here, run `<command> --help` for full options.

**Root commands**

- `dev-library api`: Call an authenticated DevLibrary JSON API endpoint.
- `dev-library outdated`: Show installed agents and standalone components with their registry status.
- `dev-library reconcile`: Backfill local session records missed by automatic hook delivery
- `dev-library scan`: Show a read-only inventory of your local harness setup.

**`dev-library admin`**: Core administration and submission review commands

- `dev-library admin review`: Submission review commands
  - `dev-library admin review approve`: Approve a component, Agent, or bundle submission.
  - `dev-library admin review list`: List pending submissions awaiting review.
  - `dev-library admin review reject`: Reject a component, Agent, or bundle submission.
  - `dev-library admin review show`: Show review details for a component or Agent.
- `dev-library admin audit-log`: Query the compliance audit log.
- `dev-library admin audit-log-export`: Export the compliance audit log as CSV or JSON.
- `dev-library admin cache-clear`: Clear all server caches.
- `dev-library admin create-user`: Create a new user account. Requires admin privileges.
- `dev-library admin delete-user`: Delete a user account. Requires admin privileges.
- `dev-library admin diagnostics`: Show system diagnostics and health status.
- `dev-library admin reset-password`: Reset a user's password. Requires admin privileges.
- `dev-library admin saml-config`: View current SAML SSO configuration.
- `dev-library admin saml-config-delete`: Delete SAML SSO configuration. Disables SAML SSO.
- `dev-library admin saml-config-set`: Create or update SAML SSO configuration.
- `dev-library admin scim-token-create`: Create a new SCIM provisioning token.
- `dev-library admin scim-token-revoke`: Revoke a SCIM provisioning token.
- `dev-library admin scim-tokens`: List SCIM provisioning tokens.
- `dev-library admin security-events`: View security events log.
- `dev-library admin set`: Set a server setting.
- `dev-library admin set-role`: Change a user's role.
- `dev-library admin settings`: List server settings.
- `dev-library admin trace-privacy`: View trace privacy setting.
- `dev-library admin trace-privacy-set`: Enable or disable trace privacy (redacts sensitive trace data).
- `dev-library admin users`: List all users.

**`dev-library agent`**: Agent registry commands

- `dev-library agent co-authors`: Manage co-authors for agents
  - `dev-library agent co-authors add`: Add a co-author.
  - `dev-library agent co-authors list`: List co-authors.
  - `dev-library agent co-authors remove`: Remove a co-author.
- `dev-library agent add`: Add a component reference to observal-agent.yaml.
- `dev-library agent archive`: Archive an agent.
- `dev-library agent build`: Validate agent definition against the server (dry-run).
- `dev-library agent bulk-create`: Bulk-create agents from a JSON file.
- `dev-library agent create`: Create a new agent (interactive wizard, from file, or via flags).
- `dev-library agent delete`: Archive an agent. Prefer the archive command.
- `dev-library agent init`: Scaffold an observal-agent.yaml definition file.
- `dev-library agent install`: Get install config for an agent.
- `dev-library agent list`: List active agents (paginated).
- `dev-library agent my`: List your own agents (all statuses).
- `dev-library agent publish`: Publish the agent definition to the server.
- `dev-library agent pull`: Fetch agent config and write harness files to disk.
- `dev-library agent release`: Bump version and push a versioned release to the registry.
- `dev-library agent show`: Show full agent details.
- `dev-library agent transfer-owner`: Transfer ownership to another username.
- `dev-library agent unarchive`: Restore an archived agent back to active status.
- `dev-library agent versions`: List all versions for an agent.

**`dev-library auth`**: Authentication and account commands

- `dev-library auth login`: Connect to Observal.
- `dev-library auth logout`: Clear saved credentials.
- `dev-library auth whoami`: Show current authenticated user.
- `dev-library auth status`: Check authenticated server connectivity and local outbox health.
- `dev-library auth change-password`: Change your password.
- `dev-library auth set-username`: Set or update your username.

**`dev-library config`**: CLI configuration

- `dev-library config alias`: Set or remove a local registry reference alias.
- `dev-library config aliases`: List all local aliases.
- `dev-library config path`: Show the config file path.
- `dev-library config set`: Set a validated user-managed CLI setting.
- `dev-library config show`: Show effective CLI configuration without exposing credentials.

**`dev-library doctor`**: Diagnose and patch harness settings for DevLibrary telemetry

- `dev-library doctor support`: Generate and inspect diagnostic support bundles. Bundles contain no customer data or row contents.
  - `dev-library doctor support bundle`: Generate a diagnostic support bundle. No customer data or row contents included.
  - `dev-library doctor support inspect`: Inspect a support bundle without extracting it.
- `dev-library doctor cleanup`: Remove DevLibrary-managed telemetry artifacts while preserving user configuration.
- `dev-library doctor patch`: Install DevLibrary-managed session telemetry for selected harnesses.

**`dev-library inbox`**: Your work and event feed: reviews, decisions, and update notices

- `dev-library inbox count`: Show unread and needs-action counts.
- `dev-library inbox dismiss`: Dismiss an item without acting on it.
- `dev-library inbox done`: Resolve an item.
- `dev-library inbox list`: List your inbox items.
- `dev-library inbox read`: Mark an item read without resolving it.
- `dev-library inbox read-all`: Mark everything matching the filter as read.
- `dev-library inbox reopen`: Reopen a resolved or dismissed item.
- `dev-library inbox show`: Show one item with its full action history.
- `dev-library inbox unread`: Mark an item unread again.

**`dev-library ops`**: Observability and operational commands (sessions, telemetry, rankings, feedback, insights)

- `dev-library ops insights`: Agent insight reports
  - `dev-library ops insights generate`: Trigger generation of a new insight report.
  - `dev-library ops insights list`: List insight reports for an agent.
  - `dev-library ops insights show`: Show an insight report with pretty-printed narrative.
- `dev-library ops logs`: Live log viewer (open in a separate tab)
- `dev-library ops telemetry`: Telemetry health commands
  - `dev-library ops telemetry status`: Check telemetry data flow status.
- `dev-library ops feedback`: Show feedback for an MCP server or agent.
- `dev-library ops rate`: Rate an MCP server, agent, or component.
- `dev-library ops rate-delete`: Delete your review for an item.
- `dev-library ops rate-update`: Update your existing review for an item.
- `dev-library ops top`: Show top MCP servers or agents by usage.
- `dev-library ops traces`: List recent traces (sessions).

**`dev-library registry`**: Component registry (MCPs, skills, hooks, prompts, sandboxes)

- `dev-library registry bulk`: Submit mixed Registry components from one JSON file.
  - `dev-library registry bulk submit`: Submit mixed MCP, skill, hook, prompt, and sandbox entries.
- `dev-library registry hook`: Hook registry commands
  - `dev-library registry hook co-authors`: Manage co-authors for hooks
    - `dev-library registry hook co-authors add`: Add a co-author.
    - `dev-library registry hook co-authors list`: List co-authors.
    - `dev-library registry hook co-authors remove`: Remove a co-author.
  - `dev-library registry hook archive`: Archive this component.
  - `dev-library registry hook edit`: Edit a draft, rejected, or pending hook submission.
  - `dev-library registry hook install`: Install a hook for a specific harness.
  - `dev-library registry hook list`: List approved hooks from the registry.
  - `dev-library registry hook show`: Show detailed information for a single hook.
  - `dev-library registry hook submit`: Submit a new hook for review.
  - `dev-library registry hook transfer-owner`: Transfer ownership to another username.
  - `dev-library registry hook unarchive`: Restore an archived component.
- `dev-library registry mcp`: MCP server registry commands
  - `dev-library registry mcp co-authors`: Manage co-authors for mcps
    - `dev-library registry mcp co-authors add`: Add a co-author.
    - `dev-library registry mcp co-authors list`: List co-authors.
    - `dev-library registry mcp co-authors remove`: Remove a co-author.
  - `dev-library registry mcp submit`: Submit an MCP server to the registry.
  - `dev-library registry mcp show`: Show full details of an MCP server.
  - `dev-library registry mcp install`: Generate an install config snippet for an MCP server.
  - `dev-library registry mcp archive`: Archive this component.
  - `dev-library registry mcp edit`: Edit an MCP server submission.
  - `dev-library registry mcp list`: List approved MCP servers in the registry.
  - `dev-library registry mcp my`: List your own MCP servers across all statuses.
  - `dev-library registry mcp transfer-owner`: Transfer ownership to another username.
  - `dev-library registry mcp unarchive`: Restore an archived component.
- `dev-library registry models`: Inspect registry-backed harness model data.
  - `dev-library registry models list`: List registry-backed harness models.
- `dev-library registry prompt`: Prompt registry commands
  - `dev-library registry prompt co-authors`: Manage co-authors for prompts
    - `dev-library registry prompt co-authors add`: Add a co-author.
    - `dev-library registry prompt co-authors list`: List co-authors.
    - `dev-library registry prompt co-authors remove`: Remove a co-author.
  - `dev-library registry prompt archive`: Archive this component.
  - `dev-library registry prompt edit`: Edit a draft, rejected, or pending prompt submission.
  - `dev-library registry prompt list`: List approved prompts in the registry.
  - `dev-library registry prompt my`: List your own prompts across all statuses.
  - `dev-library registry prompt render`: Render a prompt template with variable substitution.
  - `dev-library registry prompt show`: Show detailed information about a prompt.
  - `dev-library registry prompt submit`: Submit a new prompt template for review.
  - `dev-library registry prompt transfer-owner`: Transfer ownership to another username.
  - `dev-library registry prompt unarchive`: Restore an archived component.
- `dev-library registry recommend`: Components recommended for you, based on your own sessions
  - `dev-library registry recommend dismiss`: Stop recommending a component to you.
  - `dev-library registry recommend list`: Show components recommended for you.
- `dev-library registry sandbox`: Sandbox registry commands
  - `dev-library registry sandbox co-authors`: Manage co-authors for sandboxes
    - `dev-library registry sandbox co-authors add`: Add a co-author.
    - `dev-library registry sandbox co-authors list`: List co-authors.
    - `dev-library registry sandbox co-authors remove`: Remove a co-author.
  - `dev-library registry sandbox archive`: Archive this component.
  - `dev-library registry sandbox edit`: Edit a draft, rejected, or pending sandbox submission.
  - `dev-library registry sandbox list`: List approved sandboxes in the registry.
  - `dev-library registry sandbox show`: Show detailed information about a sandbox.
  - `dev-library registry sandbox submit`: Submit a new sandbox environment for review.
  - `dev-library registry sandbox transfer-owner`: Transfer ownership to another username.
  - `dev-library registry sandbox unarchive`: Restore an archived component.
- `dev-library registry skill`: Skill registry commands
  - `dev-library registry skill co-authors`: Manage co-authors for skills
    - `dev-library registry skill co-authors add`: Add a co-author.
    - `dev-library registry skill co-authors list`: List co-authors.
    - `dev-library registry skill co-authors remove`: Remove a co-author.
  - `dev-library registry skill archive`: Archive this component.
  - `dev-library registry skill edit`: Edit a draft, rejected, or pending skill submission.
  - `dev-library registry skill install`: Install a skill by fetching the full skill directory from git.
  - `dev-library registry skill list`: List approved skills in the registry.
  - `dev-library registry skill my`: List your own skills across all statuses.
  - `dev-library registry skill show`: Show detailed information about a skill.
  - `dev-library registry skill submit`: Submit a new skill for review.
  - `dev-library registry skill transfer-owner`: Transfer ownership to another username.
  - `dev-library registry skill unarchive`: Restore an archived component.
- `dev-library registry version`: Manage component versions
  - `dev-library registry version list`: List version history for a registry component.
  - `dev-library registry version publish`: Publish a new version for a registry component.

**`dev-library self`**: CLI self-management commands (upgrade, downgrade, rollback, status)

- `dev-library self upgrade`: Upgrade the DevLibrary CLI to the latest or specified version.
- `dev-library self downgrade`: Downgrade the DevLibrary CLI to a previous version.
- `dev-library self rollback`: Restore the CLI binary saved before the last version change.
- `dev-library self status`: Show the CLI version, install method, and update availability.

**`dev-library server`**: Manage the embedded DevLibrary server (PostgreSQL + ClickHouse + Redis + API).

- `dev-library server migrate`: Portable PostgreSQL and ClickHouse migration tools
  - `dev-library server migrate export`: Export all PostgreSQL registry data to a portable archive.
  - `dev-library server migrate export-telemetry`: Export ClickHouse telemetry data to Parquet files.
  - `dev-library server migrate import`: Import a migration archive into the target database.
  - `dev-library server migrate import-telemetry`: Import Parquet telemetry files into target ClickHouse.
  - `dev-library server migrate validate`: Validate archive integrity and optionally compare against a database.
  - `dev-library server migrate validate-telemetry`: Validate telemetry Parquet files and optionally check FK references.
- `dev-library server start`: Start the embedded services and API.
- `dev-library server stop`: Stop all embedded services.
- `dev-library server restart`: Restart all embedded services.
- `dev-library server status`: Show embedded service status.
- `dev-library server logs`: Show embedded service logs.
- `dev-library server install`: Download verified embedded database binaries.
- `dev-library server reset`: Stop embedded services and wipe database data and generated secrets.
- `dev-library server config`: Show embedded server paths and ports.
- `dev-library server rollback`: Restore PostgreSQL and the Docker image version from backup.
- `dev-library server upgrade`: Upgrade a local Docker deployment.
- `dev-library server versions`: List Docker image versions and managed PostgreSQL backups.

**`dev-library team`**: Manage teamspaces: creation, membership, access, and visibility.

- `dev-library team invite`: Manage private-team invitation links.
  - `dev-library team invite create`: Create a private-team invitation link. Owner or global admin only.
  - `dev-library team invite delete`: Delete an unused invitation. Owner or global admin only.
  - `dev-library team invite list`: List invitation links for a private teamspace.
  - `dev-library team invite preview`: Preview an invitation without requesting access.
  - `dev-library team invite request`: Use an invitation to request access. An owner must still approve.
  - `dev-library team invite requests`: List access requests associated with an invitation.
  - `dev-library team invite revoke`: Revoke a private-team invitation link. Owner or global admin only.
- `dev-library team members`: Manage team membership.
  - `dev-library team members add`: Add or update a team member. Owner or admin only.
  - `dev-library team members list`: List members of a teamspace.
  - `dev-library team members remove`: Remove a team member. Owner or admin only. The last owner cannot be removed.
- `dev-library team request`: Manage teamspace join requests.
  - `dev-library team request approve`: Approve a pending join request. Owner or admin only. Grants member role.
  - `dev-library team request join`: Request member access to a teamspace. An owner must approve.
  - `dev-library team request list`: List a teamspace's join requests and decisions. Owner or admin only.
  - `dev-library team request mine`: Show your join-request status for a teamspace.
  - `dev-library team request reject`: Reject a pending join request. Owner or admin only.
  - `dev-library team request withdraw`: Withdraw your pending join request for a teamspace.
- `dev-library team visibility`: Manage and review teamspace visibility.
  - `dev-library team visibility approve`: Approve pending public visibility. Reviewer or admin only.
  - `dev-library team visibility list-requests`: List pending public visibility requests. Reviewer or admin only.
  - `dev-library team visibility reject`: Reject pending public visibility. Reviewer or admin only.
  - `dev-library team visibility set`: Change visibility or request public review. Owners and admins only.
- `dev-library team claim-personal`: Claim or return your private personal teamspace.
- `dev-library team create`: Create a teamspace. Any signed-in user can; you become the owner.
- `dev-library team delete`: Delete a teamspace. Owner or admin only. This cannot be undone.
- `dev-library team leave`: Leave a teamspace. The last owner cannot leave; transfer ownership first.
- `dev-library team list`: List teamspaces you belong to (or all with --all).
- `dev-library team show`: Show teamspace detail and members.
<!-- END AUTO-GENERATED COMMAND REFERENCE -->
