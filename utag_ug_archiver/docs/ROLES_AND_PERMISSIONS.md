# Dashboard Roles and Permissions

This document outlines the different user roles in the system and what each role can do in the dashboard.

## User Roles

The system has three main user groups:
1. **Admin** - Full system access
2. **Executive** - Limited administrative access
3. **Member** - Basic access

Additionally, there are special role-based permissions:
- **Secretary** (Executive Position) - Special document management permissions
- **Superuser** - Full Django admin access (beyond Admin group)

---

## 1. ADMIN ROLE

### Permissions
- `view_dashboard` - Access to dashboard
- `view_admin`, `add_admin`, `change_admin`, `delete_admin` - Full admin management
- `view_executive`, `add_executive`, `change_executive`, `delete_executive` - Full executive management
- `view_member`, `add_member`, `change_member`, `delete_member` - Full member management
- `add_user`, `change_user`, `delete_user`, `view_user` - User management
- `add_event`, `change_event`, `delete_event`, `view_event` - Event management
- `add_news`, `change_news`, `delete_news`, `view_news` - News management
- `add_announcement`, `change_announcement`, `delete_announcement`, `view_announcement` - Announcement management
- `add_document`, `change_document`, `delete_document`, `view_document` - Document management
- `add_ad`, `change_ad`, `delete_ad`, `view_ad` - Advertisement management
- `add_adslot`, `change_adslot`, `delete_adslot`, `view_adslot` - Ad slot management
- `add_payment`, `change_payment`, `delete_payment`, `view_payment` - Payment management
- `delete_carouselslide`, `view_carouselslide` - Carousel slide management

### Dashboard Access

#### Main Menu Items:
- ✅ **Dashboard** - Full dashboard with all statistics
- ✅ **Account Management**
  - Admins (View, Create, Update, Delete, Bulk Upload)
  - Members (View, Create, Update, Delete, Bulk Upload)
- ✅ **Executives** - View and manage executive members
- ✅ **File Management** - Documents (Full CRUD access)
- ✅ **Messages** - Chat functionality
- ✅ **Site Management**
  - Events (Full CRUD)
  - Carousel Sliders (Full CRUD)
  - News (Full CRUD)
  - Gallery (Full CRUD)
  - Announcements (Full CRUD)
  - Notifications (View)
- ✅ **Advert Management**
  - Plans (Full CRUD)
  - Adverts (Full CRUD)
- ✅ **Profile** - Edit profile and change password

#### Special Capabilities:
- Can view all documents regardless of visibility settings
- Can view all announcements (including drafts)
- Can see all statistics on dashboard
- Can manage all user accounts
- Can create/update/delete all content types
- Can access advertisement management

---

## 2. EXECUTIVE ROLE

### Permissions
- `view_dashboard` - Access to dashboard
- `view_member` - View members list
- `view_document` - View documents
- `view_event`, `view_news` - View events and news
- `add_announcement`, `change_announcement`, `delete_announcement`, `view_announcement` - Announcement management
- `view_notification` - View notifications

### Dashboard Access

#### Main Menu Items:
- ✅ **Dashboard** - Limited dashboard view
- ✅ **Account Management**
  - Members (View only - no create/update/delete)
- ✅ **Executives** - View executive members (if has `view_executive` permission)
- ✅ **File Management** - Documents (View only, filtered by group visibility)
- ✅ **Messages** - Chat functionality
- ✅ **Site Management**
  - Events (View only)
  - News (View only)
  - Announcements (Create, Update, Delete - can manage announcements)
  - Notifications (View)
- ✅ **Profile** - Edit profile and change password

#### Special Capabilities:
- Can create, update, and delete announcements
- Can view documents visible to Executive group
- Can view events and news
- Can view members list
- **Secretary Position Special Access:**
  - If `executive_position == "Secretary"`, can also:
    - Create, update, and delete documents
    - Create and update news (template checks `is_secretary`)
    - Create and update events (template checks `is_secretary`)

#### Restrictions:
- ❌ Cannot manage admins
- ❌ Cannot create/update/delete members
- ❌ Cannot manage events (view only)
- ❌ Cannot manage news (view only, except Secretary)
- ❌ Cannot manage carousel slides
- ❌ Cannot manage gallery
- ❌ Cannot manage advertisements
- ❌ Cannot see all documents (only group-visible ones)

---

## 3. MEMBER ROLE

### Permissions
- `view_dashboard` - Access to dashboard
- `view_document` - View documents
- `view_event`, `view_news` - View events and news
- `view_notification` - View notifications

### Dashboard Access

#### Main Menu Items:
- ✅ **Dashboard** - Basic dashboard view
- ✅ **File Management** - Documents (View only, filtered by group visibility)
- ✅ **Messages** - Chat functionality
- ✅ **Site Management**
  - Events (View only)
  - News (View only)
  - Announcements (View only - filtered by target groups)
  - Notifications (View)
- ✅ **Profile** - Edit profile and change password

#### Special Capabilities:
- Can view documents visible to Member group
- Can view published events
- Can view published news
- Can view announcements targeted to "everyone" or Member group
- Can access chat/messaging

#### Restrictions:
- ❌ Cannot manage any accounts (admins, members, executives)
- ❌ Cannot create/update/delete any content
- ❌ Cannot manage announcements
- ❌ Cannot manage events
- ❌ Cannot manage news
- ❌ Cannot manage carousel slides
- ❌ Cannot manage gallery
- ❌ Cannot manage advertisements
- ❌ Cannot see all documents (only group-visible ones)
- ❌ Cannot see all announcements (only targeted ones)

---

## Special Role: SECRETARY (Executive Position)

Users with `executive_position == "Secretary"` get additional permissions even if they're in the Executive group:

### Additional Capabilities:
- ✅ Can create, update, and delete documents (checked in `files.py`)
- ✅ Can create and update news (template checks `is_secretary`)
- ✅ Can create and update events (template checks `is_secretary`)
- ✅ Can manage announcements (already has this as Executive)

### How It Works:
The Secretary position is checked via:
- `user.is_secretary()` - Checks if user is in "Secretary" group
- `user.executive_position == "Secretary"` - Checks executive position field

---

## Document Visibility Rules

Documents have visibility settings that determine who can see them:

1. **Everyone** - All authenticated users can view
2. **Selected Groups** - Only users in specified groups can view

### Access Logic:
- **Admin/Superuser**: Can view all documents regardless of visibility
- **Executive/Member**: Can only view documents where:
  - Visibility is "everyone", OR
  - Visibility is "selected_groups" AND their group is in the selected groups

---

## Announcement Access Rules

Announcements have target settings:

1. **Everyone** - All users can view
2. **Specific Groups** - Only specified groups can view

### Access Logic:
- **Admin**: Can view all announcements (including drafts)
- **Executive/Secretary**: Can view announcements where:
  - Target is "everyone", OR
  - Target includes Executive group
  - Can also see their own drafts
- **Member**: Can view announcements where:
  - Target is "everyone", OR
  - Target includes Member group
  - Can also see their own drafts

---

## Profile Management

All roles can:
- ✅ Update their profile information (title, name, phone)
- ✅ Change their profile picture
- ✅ Change their password (requires current password, except superuser/admin)

---

## Permission Checking Methods

The system uses multiple methods to check permissions:

1. **Django Permissions**: `user.has_perm('app.permission')`
2. **Group Membership**: `user.groups.filter(name='GroupName').exists()`
3. **Helper Methods**: 
   - `user.is_admin()` - Checks Admin group or superuser
   - `user.is_executive()` - Checks Executive group
   - `user.is_member()` - Checks Member group
   - `user.is_secretary()` - Checks Secretary group
4. **Executive Position**: `user.executive_position == "Secretary"`

---

## Notes

- Superusers have all permissions regardless of group membership
- Some views use `PermissionRequiredMixin` which automatically checks permissions
- Some views use custom logic with `@MustLogin` decorator and manual permission checks
- Templates use `{% if perms.app.permission %}` and `{% if user.is_admin %}` for conditional rendering

