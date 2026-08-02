# Legacy dashboard parity audit

Audit date: 23 July 2026

This audit compares the active Django dashboard and chat routes in
`utag_ug_archiver/` with the current FastAPI and Next.js portal in `apps/`.
Commented-out legacy committee routes are recorded as inactive and are not
treated as missing production features.

## Status key

- **Complete** — the current portal supports the legacy capability.
- **Modernized** — the capability exists with a safer or more auditable
  workflow, so it intentionally does not behave exactly like the legacy page.
- **Open** — a verified legacy capability still needs a current equivalent.

## Account and member management

| Legacy capability | Current status | Current implementation or remaining gap |
| --- | --- | --- |
| List, search and inspect members | Complete | Members workspace, filters, sorting, paging and record drawer |
| Create a member account | Complete | Explicit **Create member** workflow; invitation email is optional |
| Edit member profile and organization placement | Complete | Edit action with college, school and department lookups |
| Upload members | Complete | CSV/XLSX preview, validation, duplicate detection, job record and secure invitations |
| Download organization reference CSV | Complete | Available directly from the import workflow |
| Export members | Complete | Protected CSV export |
| Staff ID duplicate check | Modernized | Enforced during validation/save instead of a separate legacy lookup page |
| Reset a member password | Modernized | **Reset password** invalidates the password and active sessions, creates a short-lived reset link and sends it by email. It never displays or logs a temporary password. |
| Deactivate a member | Complete | **Deactivate member** requires a reason, suspends access, revokes sessions and tokens, and records an audit event |
| Reactivate a member | Complete | **Reactivate member** restores an archived or suspended account without deleting its history |
| Sign a member out everywhere | Complete | **Sign out all devices** revokes all active sessions |
| Resend account access | Complete | **Send access link** replaces expired invitations or sends reset instructions |
| Delete a member | Modernized | **Archive member** retains historical and relational data and revokes access |
| Manage administrators | Complete | Administrators are managed in the unified Members workspace by filtering Role to Administrator; the same create, edit, access and lifecycle actions apply |
| Bulk upload administrators | Complete | The unified member import accepts `administrator` in the roles column and enforces the protected `members.roles` permission |
| Prevent privilege escalation | Complete | Creating members is separate from assigning roles; only `members.roles` can assign privileged roles or manage another administrator |
| Prevent self-lockout | Complete | Self-deactivation, self-archive, forced self-reset and self-session revocation are blocked |

### Current member permission boundaries

| Permission | Allows |
| --- | --- |
| `members.view` | View member records |
| `members.create` | Create and import ordinary member accounts |
| `members.update` | Edit profile and organization fields |
| `members.lifecycle` | Deactivate, reactivate and archive accounts |
| `members.credentials` | Reset access and revoke sessions |
| `members.export` | Export member and executive data |
| `members.roles` | Assign privileged roles and manage administrators |
| `members.permissions` | Grant and revoke auditable extra permissions on an individual member |
| `organization.manage` | Create, edit and deactivate organization units |

Members and administrators share one account workspace. An administrator is a
member whose roles include `administrator`; the unified Role filter replaces a
duplicate administrator screen.

The Secretary role receives operational member permissions but not
`members.roles` or `members.permissions`. Administrators receive all
permissions. Individual grants are added to role permissions; they cannot
override a role or delegate role/permission administration access.

## Association and publishing

| Legacy area | Current status | Current implementation or remaining gap |
| --- | --- | --- |
| Dashboard overview | Complete | Live membership, content, event, document, media, moderation and operational metrics, each block scoped to the signed-in member's permissions |
| Executive appointments | Complete | List, create from an existing searchable member, edit biography/portfolio/social data, end appointment and CSV export |
| Executive printable roster | Complete | Dedicated print-formatted current and historical roster plus CSV export |
| Organization colleges, schools and departments | Complete | Create, edit, deactivate and searchable parent selection |
| News list in dashboard | Complete | Dedicated News workspace with search, filters, create, edit, archive and moderation |
| News tags and citations | Complete | Tags and structured citation data are editable |
| News featured image | Complete | Uses a searchable list of public media that passed security scanning |
| News attached documents | Complete | Searchable selection of security-scanned public supporting documents, included in moderation and rendered on public articles |
| News publish/unpublish | Modernized | Draft/review content is approved or rejected in Moderation; published content can be withdrawn with an audit trail |
| Announcements | Complete | List, create, edit, archive, audiences and moderation |
| Events | Complete | List, detail, create, edit, archive, registration controls, speakers, schedule, organizer and access rules |
| Event featured image | Complete | Uses security-scanned media |
| Event supplementary documents/images and photos link | Complete | Searchable scanned supporting-media selection and photos URL, included in moderation and rendered on public event pages |
| Public-site content moderation | Complete | Review queue, safe preview, approve, reject with required reason, withdraw and immutable audit events |
| Homepage carousel | Complete | Create, edit and archive slides using searchable, scanned public images |
| Galleries | Modernized | Gallery CRUD is complete; images are uploaded once in central Media, security-scanned, then selected through a searchable multi-picker |

### Dashboard overview scoping

The overview endpoint returns only the blocks the signed-in member may see, and
names them in a `sections` field so an empty block means "no data" rather than
"not authorized".

| Overview block | Required permission |
| --- | --- |
| Active member count | `members.view` |
| Document count | `documents.view`; non-managers are counted against document audience rules |
| Upcoming events | Everyone; restricted to published events without `events.manage` |
| Unread updates and recent notifications | Everyone; scoped to the signed-in member |
| Recent activity ledger | `audit.view` |
| Association pulse chart | `audit.view` or `analytics.view` |
| Own executive appointment | Shown when the member holds an active appointment |

## Documents, communications and operations

| Legacy area | Current status | Current implementation or remaining gap |
| --- | --- | --- |
| Documents list/detail/create/edit/delete | Modernized | Access-aware documents, immutable versions, retention/legal-hold metadata, secure downloads and archive instead of destructive deletion |
| Several files attached to one document revision | Complete | Each immutable document revision accepts one or more scanned files and exposes the complete current bundle |
| Profile details, profile image and password | Complete | Profile editor, searchable organization placement, security settings, password change and personal session management |
| Active executive public profile | Complete | The Profile page restores the legacy self-service biography and social-link editor for the member's current appointment; the biography uses the rich-text editor and updates the public leadership profile |
| Notifications list/detail/read/delete | Modernized | Inbox, unread count, mark one/all read, archive and permission-protected association send |
| Direct chat | Complete | Searchable member directory, start conversation, read receipts and message deletion |
| Group chat create/rename/members/admin/leave | Complete | Owners and administrators can add, remove and promote members; members can leave |
| Chat file attachments and thumbnails | Complete | Chat members upload attachments through private security scanning; authorized participants can preview images or open files |
| Group invitation links | Complete | Group owners/admins create expiring secure links; authenticated active members explicitly accept before joining |
| Advertising campaigns | Complete | Campaign CRUD, scheduling, placement, scanned creative, status and performance |
| Advertising placements | Complete | Placement CRUD and creative dimensions |
| Advertising plans | Complete | Plan CRUD, pricing, duration and activation |
| Advertising orders | Complete | Order CRUD with searchable advertiser, plan and campaign pickers |
| Analytics, audit and background jobs | Complete | These are new workspaces beyond the old dashboard |
| Portal settings and feature flags | Complete | These are new permission-protected workspaces beyond the old dashboard |

## Searchable lookup rule

All dynamic lookups and static lists with more than ten options now use a
searchable picker. This covers members, administrators, executive member
selection, organization units (including a member's Profile page), media
assets, gallery images, advertising placements, advertisers, plans and
campaigns. Short controlled lists such as gender or workflow status remain
simple selects.

Lookup loading, empty, error, clear-selection and retry states are explicit.
Required searchable values are validated before submission, so a failed lookup
cannot silently submit an empty identifier.

Member and media searches are also filtered by the API after a short debounce,
so records beyond the first loaded page remain discoverable when these datasets
grow.

## Dashboard authoring-field rule

Every dashboard create, edit and action form is covered by an automated field
classification audit.

- The full rich-text editor is used for executive biographies both in the
  appointment workspace and an active executive's own Profile page, news
  bodies, announcement messages, event full descriptions, document
  descriptions, gallery introductions, homepage carousel copy and manually
  sent notification messages.
- Primary publishing titles use a full-width, prominent input on create and
  edit forms for news, announcements, events, documents, galleries, carousel
  slides and advertising campaigns. The notification composer follows the same
  rule.
- Short summaries and excerpts remain plain text so cards, metadata and search
  results stay concise.
- Repeatable citation notes, speaker biographies and event-schedule
  descriptions use full-width multiline fields while remaining plain text,
  because their structured public components do not accept embedded HTML.
- Addresses, media alternative text and captions, moderation reasons, version
  notes, advertising order notes, feature-flag descriptions and private chat
  messages remain plain text because they are operational or accessibility
  fields rather than formatted publications.
- Rich HTML is sanitized at the API boundary and rendered as formatted content
  in dashboard details and every applicable public view; raw HTML tags are not
  shown to staff or visitors.

## Intentional differences from the legacy dashboard

The following legacy behavior must not be restored:

1. Password resets that reveal a generated password to the administrator.
2. Destructive deletion of member, content, document or media history.
3. Direct publishing without review where moderation is required.
4. Role assignment through the general member-create permission.
5. Raw UUID/ID entry when the related record can be selected safely.
6. File selection before security scanning completes.

## Verified remaining work

No active legacy dashboard capability remains marked open in this audit.

Feature parity does not mean the legacy production records are already present
in a new local database. The local environment must still run the documented
zero-loss migration against an authorized read-only legacy database snapshot,
then reconcile counts and hashes before cutover. Until that migration is run,
an empty local member/content list is expected and must not be described as a
completed data migration.
