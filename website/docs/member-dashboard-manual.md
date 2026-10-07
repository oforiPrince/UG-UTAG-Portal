# UG UTAG member and administrator dashboard manual

**Audience:** UG UTAG members, executive officers, secretariat staff, content
editors, and administrators.

**Portal:** Open the UG UTAG public website and select **Member portal**, or go
directly to `/login` on the deployed site.

## 1. First sign-in

1. Enter the email address on your UG UTAG account and the temporary password
   supplied through the approved invitation route.
2. Select **Sign in securely**.
3. If the account has a temporary credential, the portal opens **Profile** and
   requires a private replacement password before normal dashboard work.
4. Enter the current temporary password, then a new password of at least 12
   characters containing uppercase and lowercase letters and a number.
5. Confirm the new password and select **Update password**.

Never share a password in email, chat, screenshots, or support tickets. Use
**Forgot password?** on the sign-in screen if the credential is unavailable.
The recovery response is intentionally generic and does not reveal whether an
email address has an account.

## 2. Dashboard layout and live status

The dashboard uses the same responsive application on desktop, tablet, and
phone:

- the header shows the current workspace, live connection state, theme control,
  notification link, and profile link;
- desktop navigation appears in the left rail;
- phone navigation keeps the primary workspaces at the bottom and places the
  full menu under **More**;
- **Live** means the shared WebSocket connection is active and permitted changes
  can refresh the current workspace without a manual reload;
- **Reconnecting** means the current information may be stale until REST
  reconciliation finishes.

Search, filters, sortable column headings, bounded pagination, refresh, empty
states, and detail drawers follow the same pattern across administration pages.
Buttons are shown only when the signed-in role has the corresponding permission.

## 3. Everyday member workflows

### Overview

Open **Overview** for role-aware membership totals, upcoming events, unread
notifications, and the Association Pulse activity stream. Values show their
freshness and update from committed server data.

### Profile and password

Open the initials/profile link in the header. Update title, name, gender,
academic rank, phone number, and organization placement, then select **Save
profile**. The password panel always requires the current password. Organization
options are controlled by administrators.

### Documents and resources

Open **Documents** to search association records. Select a row to review its
metadata and use **Open file** or a version action when permitted. Private files
are served only after fresh authorization; knowing a file link does not grant
access.

### Events, news, and announcements

Use **Events**, **Articles**, and **Announcements** for the records visible to
your role. Public news and event pages remain available from the public-site
navigation.

### Notifications

Open **Notifications** to read targeted association notices. Individual items
and **Mark all read** synchronize through the API and live event stream.

### Chat

Open **Chat** to start a direct conversation with a member or create a managed
group when permitted. Group administrators can rename a group, add or remove
members, and assign group administrators. Conversation membership is enforced
by the server for history, messages, receipts, and WebSocket subscriptions.

## 4. Administrator workflows

### Members

The **Members** workspace provides search, status filters, sorting, details,
edit, invite, access-link, deactivate/reactivate, permanent delete, import, and
export actions.

To import members:

1. Select **Import** and choose a `.csv` or `.xlsx` file no larger than 8 MB
   with at most 2,000 data rows.
2. Include `email`, `other_name`, and `surname`. Optional columns are
   `staff_id`, `title`, `gender`, `academic_rank`, `phone_number`, and `roles`.
3. Separate multiple roles with commas or semicolons. Supported role keys are
   `member`, `executive`, `editor`, `publisher`, `secretary`, and
   `administrator`.
4. Select **Preview rows**. Review valid rows, duplicates, unknown roles,
   missing values, and every row-level issue.
5. Correct the source file and preview again until the result is acceptable.
6. Select **Import and invite** only after review. The import is atomic: invalid
   rows are not partially mixed into a successful batch.

Preview never creates accounts. A committed import creates invited accounts,
records audit/job evidence, and queues invitations. Existing emails or staff
IDs are reported rather than overwritten.

Use **Export** for the authorized CSV view. Spreadsheet-formula prefixes are
escaped before download. Use **Deactivate member** to suspend access while
retaining the account and its history. Use **Delete member** only for an
unneeded account with no shared history. Permanent Delete actions are available
only to administrators and cannot be delegated as extra access. The portal
blocks self-deletion and explains every linked appointment, message, content
record, media asset, or other dependency that must be resolved first.

### Executive officers and councils

Open **Executives** to create an appointment from an existing member, record
position, portfolio, biography, appointment dates, term, acting state, active
state, and public visibility. **End appointment** preserves the term history;
**Delete appointment** permanently removes an incorrect appointment. Public
navigation presents the approved groups as **Executive Officers** and **Local
Executive Council Members**.

### Organization records

Open **Organization** to add, rename, move, reactivate, or deactivate colleges,
schools, departments, and committees. The hierarchy is **college → school →
department**; colleges and committees are top-level. Parent choices are filtered
to valid types, and moving a school or department updates linked member
affiliations in the same transaction. A unit with active children or linked
members cannot be deactivated until those records are moved, so member history
is not silently broken. **Delete unit** is permanent and is blocked while any
member, child unit, audience rule, or system-chat history is linked.

### Media library

1. Open **Media** and select **Upload asset**.
2. Choose a supported image, PDF, Office document, CSV, or text file up to the
   configured limit.
3. Add alternative text for meaningful images.
4. Leave **Private asset** selected for internal files. Clear it only for media
   approved for the public website.
5. Upload and wait for the state to become **Ready**. Quarantined, scanning, or
   rejected files cannot be published.

**Delete media** permanently removes the database record and generated-variant
links, then queues idempotent stored-file cleanup through the media worker. The
portal blocks deletion during upload scanning or while a profile, article,
event, document, gallery, advert, or carousel slide still uses the asset.

### Homepage carousel

Open **Homepage carousel** and select **New slide**. Choose a ready public image
from the media-library picker, add title/description and an optional HTTPS link,
set display order, then enable **Published**. The public homepage supplies manual
previous/next controls and does not automatically rotate. **Delete slide**
permanently removes the slide while retaining its shared media asset.

### Articles, announcements, events, documents, and galleries

Each publishing workspace uses explicit workflow state and guarded permanent
delete actions:

- **Articles:** title, excerpt, body, featured image, tags, citations, feature
  flag, publication state and time;
- **Announcements:** message, priority, audience rules, workflow state,
  publication and expiry;
- **Events:** date/time, venue or protected online details, speakers, schedule,
  registration settings, capacity, CPD credit and publication state;
- **Documents:** classification, sender/receiver, date, audience, retention,
  legal hold, scanned file and version notes;
- **Galleries:** title, description, selected media and publication state.

Open a row for its detail view. Edit actions use version/ETag protection where
provided so concurrent changes do not silently overwrite each other.
Delete removes the selected record and only its owned links; shared media is
retained. Delivery history, registrations, legal holds, and other dependencies
block deletion with a specific explanation. The server rechecks database
constraints at commit time so a concurrently added dependency also results in
a safe conflict instead of partial deletion.

### Notifications and chat administration

Use **Notifications** to send a permitted broadcast with category, priority,
title, body, deep link and audience scope. Use **Chat** for direct and group
management. All membership and message mutations are authorized and audited;
the live connection carries change events while PostgreSQL remains the durable
record.

### Advertising

Use **Placements**, **Campaigns**, **Plans**, and **Orders** to manage advert
inventory, scheduling, creative references, prices and order states. Public
placements accept only server-defined media and links—never arbitrary script or
unsanitized advert HTML.

### Audit, settings, feature flags, and jobs

- **Audit** records security and administrative changes with actor, action,
  resource, outcome and request context.
- **Settings** controls public and operational values without exposing secrets.
- **Feature flags** provides controlled rollout switches.
- **Jobs** shows durable background-work state, input/output summaries and
  failures.

## 5. Safe operating rules

- Use deactivate, end, complete, cancel, or workflow status changes when
  history must be retained. Use Delete only for records that should be removed
  permanently. Delete is administrator-only and cannot be delegated.
- Do not paste production secrets, passwords, private document links, or raw
  member exports into tickets or chat.
- Make public media non-private only after rights, alternative text, and content
  approval.
- Review the target record and consequence shown by every high-risk
  confirmation.
- Do not retry a slow import or publication repeatedly; check **Jobs** and the
  live status first.
- Report unexpected permission access, missing migrated data, or file checksum
  concerns immediately and do not attempt an ad-hoc database correction.

## 6. Troubleshooting

**Sign-in fails:** Confirm the exact account email, keyboard case, and temporary
credential. Use password recovery rather than asking an administrator to reveal
the stored password.

**A page looks stale:** Check the header. If it shows reconnecting, wait for the
live indicator or select **Refresh** once. Persistent failures should include
the page name, time, and visible request ID—not a password or private record.

**An upload is unavailable:** Check its media state. It must complete scanning
and become **Ready**. A rejected file should be replaced from a trusted source,
not renamed to bypass validation.

**A carousel image is missing:** Confirm the asset is an image, is public, and
has `Ready` state. It will then appear by filename in the carousel picker.

**An import reports errors:** Download or review the row issues, correct the
original spreadsheet, and run preview again. Previewing is safe and makes no
account changes.

**Access is denied:** Request the correct role through the UG UTAG secretariat.
Frontend visibility does not override server authorization.
