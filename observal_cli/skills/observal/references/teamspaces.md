<!-- SPDX-FileCopyrightText: 2026 DevLibrary Contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Teamspace workflows

## Contents

- Discover and create
- Visibility review
- Join requests
- Members
- Private invitations
- Destructive operations

Use team UUIDs or handles returned by JSON. Never select a teamspace or request by table position.

## Discover and create

```bash
dev-library team list --output json
dev-library team list --all --output json
dev-library team show platform-tools --output json
dev-library team claim-personal --output json
dev-library team create 'Platform Tools' --handle platform-tools --visibility private --output json
```

`claim-personal` is idempotent. Public creation enters review and can return `visibility: private` with `visibility_request_status: pending`. Report both fields.

## Visibility review

Owners request a visibility change:

```bash
dev-library team visibility set platform-tools public --output json
dev-library team visibility set platform-tools private --output json
```

Reviewers and admins decide public visibility:

```bash
dev-library team visibility list-requests --output json
dev-library team visibility approve platform-tools --output json
dev-library team visibility reject platform-tools --reason 'Add a public description' --output json
```

Approval can revoke private invitation links. Verify the returned visibility and review status. Rejection keeps the team private and can include a reason.

## Join requests

A user requests access and inspects their own status:

```bash
dev-library team request join platform-tools --message 'I maintain deployments' --output json
dev-library team request mine platform-tools --output json
dev-library team request withdraw platform-tools --yes --output json
```

Withdrawal automatically finds the caller's sole pending request. JSON withdrawal requires `--yes`.

Owners and admins review requests:

```bash
dev-library team request list platform-tools --status pending --output json
dev-library team request approve platform-tools @alice --output json
dev-library team request reject platform-tools bob@example.com --reason 'Use the SRE teamspace' --output json
```

Approving grants member role. Approve and reject match an exact email or case-insensitive username. Verify the returned request status and resulting membership when approval matters.

## Members

```bash
dev-library team members list platform-tools --output json
dev-library team members add platform-tools alice@example.com --role reviewer --output json
dev-library team members add platform-tools @bob --role owner --output json
dev-library team members remove platform-tools @bob --yes --output json
```

Roles are `member`, `reviewer`, and `owner`. Adding an existing member updates the role. The last owner cannot leave or be removed.

## Private invitations

Owners create and inspect invitation links:

```bash
dev-library team invite create platform-tools --name onboarding --expires-days 30 --max-uses 20 --output json
dev-library team invite list platform-tools --output json
dev-library team invite requests platform-tools INVITE_UUID --output json
```

Creation returns a one-time token and URL. Treat the entire response as secret. Do not put the token in logs or final prose.

Recipients preview a token and request access:

```bash
dev-library team invite preview INVITE_TOKEN --output json
dev-library team invite request INVITE_TOKEN --message 'I am joining the deployment rotation' --output json
```

Preview does not mutate state. Request creates a pending join request and does not grant membership. An owner must approve it.

## Destructive operations

```bash
dev-library team invite revoke platform-tools INVITE_UUID --yes --output json
dev-library team invite delete platform-tools INVITE_UUID --yes --output json
dev-library team leave platform-tools --yes --output json
dev-library team delete platform-tools --yes --output json
```

Revoke preserves invitation audit history. Delete succeeds only for an unused invitation without request history. Team deletion is permanent. Verify state after every destructive operation.
