# MASTER IMPLEMENTATION PROMPT  
## Build the Complete VIP Frontend Application

Act as a Principal Frontend Architect, Staff Vue Engineer, Enterprise UX Engineer, and SaaS Product Design Lead.

Your task is to build the complete production-quality frontend application for:

# VIP — Veltrix Intelligence Platform

VIP is an AI-native, multi-tenant enterprise platform combining:

- Data connectivity
- Data integration
- Pipeline engineering
- Dataset management
- Semantic modeling
- Business intelligence
- Dashboards
- Reports
- AI assistants
- AI agents
- Workflow automation
- Notifications
- Administration
- Billing
- Governance
- Developer APIs
- Marketplace capabilities

This is not a UI concept exercise.

This is not a wireframe task.

This is not a documentation-only task.

You must implement the real frontend application inside the existing repository.

The result must be a complete, navigable, responsive, accessible, testable frontend that is ready to connect to backend APIs as those APIs become available.

---

# 1. Source of Truth

Before changing code:

1. Read the entire repository.
2. Read all project documentation.
3. Read the attached VIP implementation roadmap.
4. Read the product requirements and design-system documents.
5. Inspect the existing monorepo structure.
6. Inspect the existing frontend application.
7. Inspect the shared UI package.
8. Inspect authentication, organization, workspace, RBAC, API-client, and routing foundations.
9. Inspect existing dependencies before adding new ones.
10. Identify what has already been implemented and reuse it.

Do not duplicate existing work.

Do not replace working architecture without a strong technical reason.

Do not ignore existing coding standards.

---

# 2. Primary Objective

Build the complete frontend for VIP so that every planned platform module has:

- A real route
- A real application page
- A coherent layout
- Real reusable components
- Real navigation
- Real user interactions
- Forms
- Tables
- Drawers
- Dialogs
- Empty states
- Loading states
- Error states
- Permission states
- Responsive behavior
- Accessibility behavior
- Mock service integration where backend APIs are unavailable
- Typed API contracts
- Clear backend integration points
- Automated tests

The frontend must be structurally ready for the full VIP backend.

The backend team must be able to connect real APIs later without rebuilding the UI.

---

# 3. Important Execution Rule

Do not attempt to write the entire frontend as one unstructured code dump.

Treat this as a complete frontend implementation program.

Execute it in ordered implementation batches.

At the beginning:

1. Produce a repository assessment.
2. Produce a frontend architecture plan.
3. Produce a route inventory.
4. Produce a module inventory.
5. Produce a shared-component inventory.
6. Identify backend dependencies.
7. Identify safe mock boundaries.
8. Identify risks and missing prerequisites.

Then implement the work continuously in the correct dependency order.

Do not stop after planning.

Do not ask for approval after every batch.

Proceed through the full frontend scope unless a genuine technical blocker makes implementation impossible.

---

# 4. Technical Direction

Use the repository’s existing frontend stack.

The expected frontend stack is:

- Vue 3
- TypeScript
- Vite or the existing application builder
- Vue Router
- Pinia only where global client state is justified
- TanStack Query for server state if already selected
- Existing styling framework
- Existing UI package
- Existing validation libraries
- Existing testing tools
- Existing monorepo package manager

Do not introduce React.

Do not create a second frontend application unless the repository architecture explicitly requires it.

Do not replace existing dependencies unnecessarily.

Use strict TypeScript.

Avoid `any`.

Use typed component props, emits, routes, APIs, form schemas, commands, permissions, and feature flags.

---

# 5. Frontend Architecture Requirements

The frontend must follow these boundaries:

## Server State

Use a query and mutation layer for:

- API requests
- Query caching
- Pagination
- Filtering
- Sorting
- Retry
- Request cancellation
- Cache invalidation
- Optimistic updates where safe

## Global Client State

Use global state only for:

- Authenticated user
- Active organization
- Active workspace
- Theme
- Locale
- Sidebar preferences
- Global notification count
- Feature flags
- Command registry
- User preferences

Do not use global state as a dumping ground.

## Local Component State

Keep temporary UI state local, including:

- Open drawers
- Selected rows
- Active tabs
- Temporary filters
- Wizard progress
- Form fields
- Canvas selections
- Unsaved editor changes

## Domain Separation

Organize code by domain and shared responsibility.

Use a structure similar to:

- app
- router
- layouts
- shared
- components
- composables
- services
- api
- stores
- types
- permissions
- feature-flags
- mocks
- modules
  - home
  - connections
  - pipelines
  - datasets
  - semantic
  - dashboards
  - reports
  - notifications
  - ai
  - automation
  - administration
  - billing
  - audit
  - governance
  - developer
  - marketplace
  - settings

Adapt this structure to the existing repository rather than forcing a new architecture.

---

# 6. Design Language

Create one unified enterprise design language.

The visual standard should feel inspired by the quality level of:

- Microsoft Fabric
- Databricks
- Snowflake
- Linear
- Figma
- Stripe Dashboard
- GitHub Enterprise
- Azure Portal

Do not directly copy another product.

Avoid:

- Generic Bootstrap dashboards
- Cheap admin templates
- Excessive gradients
- Excessive rounded cards
- Neon startup styling
- Oversized typography
- Decorative UI that harms usability
- Inconsistent module-specific design languages

The product must feel:

- Premium
- Calm
- Intelligent
- Enterprise-grade
- Information-dense but readable
- Fast
- Consistent
- Accessible
- Scalable

---

# 7. Design Tokens and Theme System

Implement a complete token system for:

- Brand colors
- Semantic colors
- Surfaces
- Backgrounds
- Text
- Muted text
- Borders
- Focus
- Selection
- Success
- Warning
- Danger
- Information
- Data visualization colors
- Typography
- Font sizes
- Font weights
- Line heights
- Letter spacing
- Spacing
- Radius
- Shadows
- Breakpoints
- Z-index
- Motion duration
- Motion easing

Implement:

- Light theme
- Dark theme
- System theme
- Theme persistence
- Tenant branding variables
- Accessible contrast
- Visible focus states
- Reduced-motion support

Shared components must use semantic tokens.

Do not scatter hard-coded colors, spacing, shadows, or typography throughout the application.

---

# 8. Complete Application Shell

Build the authenticated VIP shell.

## Main Sidebar

Support:

- Expanded mode
- Collapsed mode
- Persistent user preference
- Nested groups
- Active route state
- Hover labels when collapsed
- Workspace-aware items
- Permission-aware items
- Feature-flag-aware items
- Mobile drawer
- Tablet behavior
- Keyboard navigation
- Scrollable navigation
- Product/version area

Main navigation groups should include:

### Core

- Home
- Favorites
- Recent activity

### Data

- Connections
- Pipelines
- Datasets
- Semantic Models
- Metrics and KPIs
- Data Quality
- Data Lineage

### Analytics

- Dashboards
- Reports
- Scheduled Deliveries

### Intelligence

- AI Assistant
- AI Studio
- Knowledge Bases
- AI Agents
- Agent Runs

### Automation

- Automations
- Automation Runs
- Approvals

### Operations

- Notifications
- Activity
- Audit Center
- Usage

### Platform

- Marketplace
- Developer Portal

### Administration

Visible only with permission:

- Platform Administration
- Organization Administration
- Workspace Administration
- Members and Roles
- Billing
- Plans and Entitlements
- Feature Flags
- Governance Policies

### Settings

- Personal Settings
- Workspace Settings
- Organization Settings
- Developer Settings
- Security

## Top Navigation

Include:

- Organization switcher
- Workspace switcher
- Breadcrumbs or current context
- Global search trigger
- Command palette trigger
- Create button or quick-action menu
- Notification entry point
- Help entry point
- User profile menu

## User Menu

Include:

- Profile
- Personal preferences
- Appearance
- Language
- Time zone
- Security
- Keyboard shortcuts
- Sign out

---

# 9. Layout System

Implement reusable layouts for:

- Authenticated application
- Standard list page
- Standard detail page
- Full-width studio
- Canvas editor
- Settings
- Administration
- Billing
- Wizard
- Blank focused task
- Authentication
- Public page
- Error page
- Fullscreen preview
- Split-pane workspace

Create reusable page primitives for:

- Page header
- Breadcrumbs
- Title
- Description
- Resource status
- Primary actions
- Secondary actions
- Tabs
- Secondary navigation
- Filters
- Content container
- Right-side inspector
- Bottom console
- Sticky toolbar
- Resizable panel
- Collapsible panel

Studio layouts must support:

- Left resource palette
- Center canvas
- Right inspector
- Bottom logs or results panel
- Resizing
- Collapsing
- Fullscreen mode
- Persistent panel sizes where appropriate

---

# 10. Routing and Route Governance

Create a complete route hierarchy.

Every route must support typed metadata such as:

- Requires authentication
- Requires organization
- Requires workspace
- Required permission
- Required role
- Required feature flag
- Required entitlement
- Layout type
- Page title
- Breadcrumb definition
- Navigation group
- Search keywords

Implement route behavior for:

- Unauthenticated
- Unauthorized
- Forbidden
- Not found
- Invalid organization
- Invalid workspace
- Suspended tenant
- Disabled tenant
- Missing entitlement
- Feature unavailable
- Configuration required
- Session expired

Support:

- Deep links
- Intended-route restoration after login
- Route-based code splitting
- Context preservation
- Safe redirect handling

Frontend restrictions must never be treated as the only security boundary.

---

# 11. Shared Component System

Build a complete shared UI library.

## Actions

- Primary button
- Secondary button
- Tertiary button
- Ghost button
- Icon button
- Split button
- Destructive button
- Loading button
- Button group
- Floating action where appropriate

## Forms

- Text input
- Number input
- Currency input
- Percentage input
- Search input
- Password and secret input
- Textarea
- Select
- Searchable select
- Multi-select
- Combobox
- Date picker
- Date range
- Time picker
- Time-zone selector
- Checkbox
- Radio group
- Switch
- Slider
- Tags input
- File upload
- Drag-and-drop upload
- Code editor wrapper
- JSON editor wrapper
- Key-value editor
- Expression editor foundation
- SQL editor foundation
- Form section
- Form footer
- Error summary

Each form component must support:

- Label
- Description
- Required state
- Optional state
- Error
- Warning
- Disabled
- Read-only
- Loading
- Help text
- Prefix
- Suffix
- Keyboard support
- Screen-reader support

Implement:

- Schema validation
- Dirty-state detection
- Unsaved-change protection
- Submit states
- Server validation errors
- Field-level errors
- Form-level errors

## Data Display

- Data table
- Basic table
- Virtualized table foundation
- Sorting
- Filtering
- Pagination
- Cursor pagination support
- Row selection
- Bulk actions
- Column visibility
- Column resizing
- Pinned columns
- Density controls
- Saved views
- Export actions
- Empty table
- Loading table
- Error table
- Status badge
- Tag
- Metric card
- KPI card
- Description list
- Key-value viewer
- JSON viewer
- Log viewer
- Code viewer
- Timeline
- Activity feed
- Avatar
- Avatar group
- Progress bar
- Step indicator
- Health indicator
- Sparkline foundation
- Chart container
- Accessible chart data table

## Navigation

- Tabs
- Segmented control
- Breadcrumbs
- Pagination
- Vertical navigation
- Settings navigation
- Step navigation
- Command menu
- Context menu
- Dropdown menu

## Overlays

- Modal dialog
- Alert dialog
- Destructive confirmation
- Drawer
- Side sheet
- Popover
- Tooltip
- Dropdown
- Context menu
- Command palette

Implement:

- Focus trapping
- Escape handling
- Outside-click behavior
- Focus return
- Scroll locking
- Nested overlay handling
- Async action state

## Feedback

- Toasts
- Inline alerts
- Banners
- Success messages
- Warning messages
- Validation messages
- Progress feedback
- Background-job status
- Offline indicator
- Reconnection state

---

# 12. Standard Application States

Build reusable components for:

- Initial page loading
- Skeleton loading
- Inline loading
- Button loading
- Background processing
- Empty state
- No results
- Permission denied
- Entitlement required
- Upgrade required
- Configuration required
- Connection required
- Recoverable error
- Fatal error
- Offline
- Maintenance
- Suspended tenant
- Archived workspace
- Success
- Partial success
- Retry state
- Session expired

Errors must support:

- Human-readable message
- Technical detail toggle where appropriate
- Correlation ID
- Retry
- Contact support action
- Copy diagnostics action

Unexpected frontend failures must be isolated through error boundaries.

---

# 13. Mock Backend and API-Ready Architecture

Where backend APIs do not exist:

1. Create typed frontend service interfaces.
2. Create typed request and response contracts.
3. Create mock adapters.
4. Create realistic sample data.
5. Simulate:
   - Loading
   - Success
   - Empty results
   - Validation failure
   - Permission denial
   - Server error
   - Network failure
   - Long-running jobs
6. Keep mocks separate from UI components.
7. Make switching from mock to real API configuration-driven.
8. Do not hard-code mock records directly inside pages.
9. Do not store secrets in mock browser persistence.
10. Clearly document every integration point.

Use stable resource IDs and realistic enterprise data.

Every mutation should visibly demonstrate:

- Pending state
- Success
- Error
- Cache update or invalidation
- User feedback

---

# 14. Home and Workspace Experience

Build a rich VIP home experience.

Include:

- Welcome and workspace context
- Quick actions
- Recent resources
- Favorites
- Recent activity
- Platform health summary
- Connection health
- Pipeline run summary
- Dataset freshness
- Dashboard activity
- Report delivery status
- AI usage
- Automation health
- Pending approvals
- Notifications
- Usage and quota overview
- Getting-started checklist for new workspaces

The home page must adapt by role:

- Platform administrator
- Organization owner
- Workspace administrator
- Data engineer
- Analyst
- Report author
- Business viewer
- Developer

---

# 15. Connection Studio Frontend

Build the complete Connection Studio UI.

## Pages

- Connection catalog
- Connection list
- Connection details
- Create connection wizard
- Edit connection
- Connection diagnostics
- Schema browser
- Data preview
- Connection health
- Credential rotation
- Dependency impact
- Delete or archive confirmation

## Connector Catalog

Include categories:

- Databases
- Files
- APIs
- Cloud storage
- Business applications

Include:

- Search
- Filters
- Available
- Beta
- Coming soon
- Restricted by plan
- Connector requirements
- Capabilities
- Setup documentation

Initial connector cards:

- PostgreSQL
- MySQL or MariaDB
- Microsoft SQL Server
- CSV
- Excel
- REST API
- S3-compatible storage

## Connection Wizard

Steps:

1. Select connector
2. Enter configuration
3. Add credentials
4. Test connection
5. Select resources
6. Configure settings
7. Review
8. Save

Support:

- Dynamic forms
- Secure secret handling
- Draft state without persisting secrets
- Test progress
- Structured diagnostics
- Retry
- Back
- Review summary
- Quota and entitlement states

## Connection Detail

Tabs:

- Overview
- Configuration
- Schema
- Preview
- Health
- Dependencies
- Activity
- Audit

---

# 16. Pipeline Studio Frontend

Build the complete Pipeline Studio experience.

## Pipeline List

Include:

- Search
- Status
- Owner
- Tags
- Last run
- Next schedule
- Version
- Filters
- Saved views
- Bulk actions
- Templates
- Create pipeline

## Pipeline Canvas

Implement:

- Drag and drop
- Zoom
- Pan
- Minimap
- Node selection
- Multi-select
- Edge creation
- Delete
- Duplicate
- Copy and paste
- Undo and redo
- Keyboard shortcuts
- Auto-layout foundation
- Validation markers
- Dirty state
- Autosave indicator
- Publish state
- Run action

## Node Palette

Include initial nodes:

- Source table
- Source file
- REST API source
- Select columns
- Rename columns
- Filter
- Sort
- Join
- Union
- Aggregate
- Formula
- Type conversion
- Deduplicate
- Null handling
- SQL transform
- Python transform
- Output dataset
- File export

## Node Inspector

Include:

- Configuration
- Input schema
- Output schema
- Validation
- Advanced settings
- Documentation

## Pipeline Detail Tabs

- Editor
- Runs
- Versions
- Schedules
- Dependencies
- Settings
- Activity

## Run Monitoring

Include:

- Queued
- Running
- Waiting
- Succeeded
- Failed
- Cancelled
- Timed out

Run detail must include:

- Timeline
- Node statuses
- Logs
- Metrics
- Row counts
- Duration
- Retry
- Cancel
- Correlation ID
- Inputs and outputs

---

# 17. Dataset Studio Frontend

Build:

- Dataset catalog
- Dataset list
- Dataset detail
- Dataset versions
- Schema
- Preview
- Profile
- Data quality
- Quality incidents
- Lineage
- Access
- Certification
- Activity

## Dataset Catalog

Include:

- Search
- Owner
- Workspace
- Tags
- Status
- Certification
- Source
- Freshness
- Quality score
- Favorite
- Recently used

## Dataset Detail

Tabs:

- Overview
- Data preview
- Schema
- Profile
- Quality
- Lineage
- Access
- Versions
- Activity

Include:

- Owner
- Certification
- Freshness
- Row count
- Quality score
- Source pipeline
- Downstream usage
- Sensitive-column indicators

## Data Quality

Build:

- Quality rule list
- Rule creation
- Rule editing
- Run results
- Failure trends
- Incident workflow
- Severity
- Owner
- Status
- Resolution

## Lineage

Build an interactive lineage graph with:

- Upstream connections
- Source assets
- Pipelines
- Nodes
- Datasets
- Semantic models
- Dashboards
- Reports

Provide accessible list fallback.

---

# 18. Semantic Studio Frontend

Build:

- Semantic model list
- Semantic model detail
- Model builder
- Entity editor
- Relationship editor
- Dimensions
- Measures
- Metrics
- KPIs
- Business glossary
- Version history
- Publish workflow

## Semantic Model Builder

Include:

- Dataset selection
- Entity canvas
- Relationships
- Dimensions
- Measures
- Aggregation
- Formatting
- Visibility
- Default time dimension
- Validation
- Draft
- Publish
- Version history

## Metric and KPI Builder

Support:

- Measure selection
- Aggregation
- Filters
- Time comparison
- Target
- Thresholds
- Status
- Format
- Owner
- Preview

## Business Glossary

Build:

- Term list
- Term detail
- Definition
- Owner
- Steward
- Status
- Synonyms
- Related terms
- Linked datasets
- Linked columns
- Linked metrics
- Approval state

---

# 19. Dashboard Studio Frontend

Build the complete dashboard experience.

## Dashboard List

Include:

- Search
- Favorites
- Recent
- Owner
- Status
- Updated date
- Tags
- Published state
- Templates

## Dashboard Builder

Implement:

- Drag-and-drop grid
- Resize
- Reposition
- Grid snapping
- Multi-page dashboards
- Undo and redo
- Copy and paste
- Duplicate widget
- Responsive layouts
- Draft state
- Publish
- Preview
- Share
- Version history

## Widget Library

Include:

- KPI card
- Table
- Pivot-table foundation
- Bar chart
- Line chart
- Area chart
- Pie or donut
- Scatter
- Gauge
- Progress indicator
- Text
- Rich content
- Image
- Filter control
- Date filter
- Metric comparison
- Map foundation

## Widget Configuration

Include:

- Semantic model
- Dimensions
- Measures
- Aggregation
- Filters
- Sort
- Formatting
- Labels
- Legend
- Tooltips
- Conditional formatting
- Drill behavior
- Accessible data view

## Dashboard Filters

Support:

- Global filters
- Page filters
- Widget filters
- Cross-filtering
- Drill-down
- Drill-through foundation
- Date ranges
- Saved filter state
- URL filter state
- Reset filters

## Dashboard Viewer

Build a clean published dashboard-viewing mode with:

- Filter controls
- Refresh state
- Data freshness
- Fullscreen
- Export
- Snapshot
- Subscribe
- Share
- Accessible chart data

---

# 20. Report Studio Frontend

Build:

- Report list
- Report templates
- Report builder
- Report preview
- Version history
- Approval workflow
- Export history
- Scheduled delivery

## Report Builder

Support:

- Cover page
- Header
- Footer
- Page numbering
- Text
- Tables
- Charts
- KPI blocks
- Images
- Page breaks
- Sections
- Reordering
- Report parameters
- Data binding
- Print and PDF preview

## Approval Workflow

Support:

- Draft
- In review
- Approved
- Rejected
- Published
- Reviewers
- Comments
- Decision history

## Export

Include:

- PDF
- PNG
- CSV
- Excel foundation
- Background rendering
- Progress
- Download state
- Expiration state

---

# 21. Notifications and Activity

Build:

- Notification drawer
- Notification full page
- Unread count
- Mark read
- Mark all read
- Archive
- Filter
- Severity
- Related-resource navigation
- Notification preferences

Build an activity-center experience for:

- Pipeline events
- Dataset events
- Dashboard events
- Report events
- AI events
- Automation events
- Administration events
- Billing events

---

# 22. AI Assistant Frontend

Build a production-quality workspace AI assistant.

Include:

- Conversation list
- New conversation
- Streaming response UI
- Stop generation
- Retry
- Edit and resend
- Copy
- Feedback
- Sources
- Citations
- Context selection
- Knowledge-base selection
- Dataset context
- Semantic-model context
- Model selector where permitted
- Tool-call status
- Attachment foundation
- Conversation history
- Empty state
- Error state
- Usage indicator
- AI limitations notice

Do not expose hidden chain-of-thought.

Tool execution displays should expose only safe operational summaries.

---

# 23. AI Studio Frontend

Build:

- AI Studio home
- Assistants
- Prompt templates
- Models
- Knowledge bases
- Tools
- Test sessions
- Versions
- Agent builder
- Agent runs

## Assistant Builder

Include:

- Name
- Description
- Instructions
- Model
- Knowledge sources
- Tools
- Output behavior
- Safety settings
- Version
- Draft
- Test
- Publish

## Prompt Registry

Include:

- System prompt
- Task prompt
- Output schema
- Model parameters
- Safety configuration
- Version history
- Compare
- Test
- Publish

## Knowledge Base

Include:

- Knowledge-base list
- Document upload
- Dataset source
- Processing state
- Chunking configuration
- Embedding configuration
- Indexing status
- Reindex
- Remove
- Search test
- Source citations

## Agent Builder

Include:

- Goal
- Instructions
- Model
- Knowledge
- Tools
- Memory policy
- Output schema
- Approval requirements
- Limits
- Test
- Publish

## Agent Run Detail

Include:

- Status
- Step trace
- Tool calls
- Token usage
- Cost
- Duration
- Errors
- Cancel
- Retry
- Safe logs

---

# 24. Automation Studio Frontend

Build:

- Automation list
- Automation templates
- Automation builder
- Run history
- Run detail
- Approvals
- Dead-letter view

## Automation Builder

Support:

- Trigger
- Conditions
- Branches
- Actions
- Variables
- Test
- Validate
- Draft
- Publish
- Version history

Initial triggers:

- Schedule
- Pipeline completed
- Pipeline failed
- Dataset refreshed
- Quality incident
- Connection failed
- Approval decision
- Manual trigger
- Webhook foundation

Initial actions:

- Send notification
- Send email
- Generate report
- Trigger pipeline
- Run AI agent
- Create approval
- Update metadata
- Call internal API
- External webhook foundation

## Run Monitoring

Include:

- Step status
- Inputs
- Outputs
- Logs
- Retry
- Cancel
- Resume after approval
- Duplicate-action protection state
- Dead-letter state

---

# 25. Administration Frontend

Build separate experiences for:

- Platform administrator
- Organization owner
- Organization administrator
- Workspace administrator

## Platform Administration

Build:

- Organization list
- Organization detail
- Tenant status
- Trial
- Active
- Suspended
- Disabled
- Pending deletion
- Support access or impersonation foundation
- Audit visibility
- Usage visibility
- Plan visibility

## Organization Administration

Build:

- Profile
- Legal and business information
- Owner
- Members
- Roles
- Domains
- Default workspace
- Retention settings
- Lifecycle actions
- Ownership transfer
- Danger zone

## Workspace Administration

Build:

- Workspace list
- Create
- Edit
- Archive
- Restore
- Delete
- Members
- Roles
- Defaults
- Workspace settings
- Isolation warnings
- Dependency checks

## Feature Flags

Build:

- Global flags
- Plan flags
- Organization overrides
- Workspace overrides
- Percentage rollout foundation
- Development flags
- Change history

## Governance Policies

Build settings for:

- Retention
- Data deletion
- Session duration
- MFA enforcement
- Allowed domains
- Workspace creation
- External sharing
- AI usage
- API-key usage

---

# 26. Billing Frontend

Build:

- Current plan
- Plan comparison
- Upgrade
- Downgrade
- Cancel
- Trial
- Subscription state
- Usage
- Quotas
- Payment method
- Billing contact
- Tax or VAT information
- Invoice history
- Invoice detail
- Add-ons
- Billing permissions

Clearly communicate:

- Current entitlement
- Current usage
- Remaining allowance
- Soft-limit warning
- Hard-limit reached
- Plan-change timing
- Proration foundation
- Trial conversion
- Cancellation impact

---

# 27. Audit Center

Build:

- Audit-event table
- Search
- Filters
- Actor
- Action
- Resource
- Workspace
- Organization
- Date
- IP address
- Result
- Event detail drawer
- Export state
- Redacted sensitive fields
- Correlation ID
- Before-and-after safe summaries

---

# 28. Developer Portal

Build:

- Developer overview
- API keys
- API-key creation
- Secret-show-once flow
- API-key scopes
- Rotate
- Revoke
- Webhooks
- Webhook creation
- Event subscriptions
- Delivery logs
- Replay
- Usage
- API documentation
- Quick start
- Authentication guide
- Error reference
- SDKs
- Embedding foundation

Use realistic code examples as static frontend content where appropriate.

---

# 29. Marketplace

Build:

- Marketplace home
- Search
- Categories
- Filters
- Featured items
- Connector listings
- Pipeline nodes
- Dashboard widgets
- AI tools
- Automation actions
- Templates
- Extension detail
- Compatibility
- Permissions
- Plan restrictions
- Install
- Enable
- Disable
- Upgrade
- Remove
- Dependency warning

Clearly mark:

- Available
- Installed
- Beta
- Internal
- Coming soon
- Restricted
- Incompatible

---

# 30. Settings Foundation

Build settings navigation separated into:

## Personal

- Profile
- Preferences
- Appearance
- Language
- Locale
- Time zone
- Notifications
- Security
- Sessions

## Workspace

- General
- Members
- Roles
- Defaults
- Features
- Data
- AI
- Developer

## Organization

- General
- Business information
- Members
- Roles
- Domains
- Governance
- Security
- Billing
- Usage
- Audit

## Platform Administration

- Tenants
- Plans
- Features
- Support
- System health
- Policies

Visibility must be permission-aware.

---

# 31. Command Palette and Global Search

Build a complete command palette.

Support:

- Navigation
- Recent pages
- Recent resources
- Workspace switching
- Organization switching
- Quick actions
- Create connection
- Create pipeline
- Create dashboard
- Create report
- Create automation
- Open AI Assistant
- Keyboard shortcuts
- Permission filtering
- Feature-flag filtering

Build a typed global-search provider contract.

Use mock providers for:

- Connections
- Pipelines
- Datasets
- Dashboards
- Reports
- Automations
- AI agents
- Users
- Workspaces

---

# 32. Accessibility

Target WCAG 2.1 AA.

Implement and validate:

- Keyboard navigation
- Visible focus
- Logical focus order
- Screen-reader labels
- ARIA where required
- Form-error association
- Table semantics
- Dialog focus management
- Menu semantics
- Color contrast
- Color-independent statuses
- Reduced motion
- Skip links
- Drag-and-drop keyboard alternatives
- Accessible chart data
- Touch-target sizing
- Zoom support

Critical workflows must be usable without a mouse.

---

# 33. Responsive Behavior

Support:

- Large desktop
- Standard desktop
- Laptop
- Tablet
- Mobile for supported operational workflows

Desktop and laptop are the primary experience.

Complex studios may provide a reduced mobile experience, but they must fail gracefully and explain limitations instead of rendering broken canvases.

Implement:

- Responsive sidebar
- Mobile drawer
- Adaptive top navigation
- Collapsible filters
- Responsive tables
- Card fallback where justified
- Fullscreen studio mode
- Sticky actions
- Touch-friendly controls

---

# 34. Motion

Use subtle enterprise motion.

Implement:

- Panel transitions
- Drawer transitions
- Dialog transitions
- Toast transitions
- Route-level loading transitions
- Skeleton transitions
- Expand and collapse
- Canvas selection
- Status transitions

Avoid excessive animation.

Respect reduced-motion preferences.

---

# 35. Permission, Feature and Entitlement Simulation

Create a frontend authorization model that can simulate:

- Platform administrator
- Organization owner
- Organization administrator
- Workspace administrator
- Data engineer
- Analyst
- Report author
- Business viewer
- Developer

Create development fixtures that allow role switching.

Demonstrate:

- Hidden navigation
- Disabled actions
- Forbidden routes
- Read-only resources
- Upgrade-required states
- Feature-disabled states
- Workspace isolation
- Organization isolation

Do not present frontend permission checks as backend security.

---

# 36. Quality and Testing

Add the relevant tests for:

- Components
- Composables
- Routes
- Route guards
- Navigation permissions
- Feature flags
- Entitlements
- Forms
- Validation
- Tables
- Dialog focus
- Theme behavior
- Responsive states
- Accessibility
- Error states
- Mock API behavior
- Core end-to-end journeys

Automate key frontend journeys:

1. Login simulation
2. Select organization
3. Select workspace
4. Create connection
5. Test connection
6. Browse schema
7. Create pipeline
8. Configure nodes
9. Validate
10. Publish
11. Run
12. View run status
13. Open dataset
14. Build semantic model
15. Build dashboard
16. Build report
17. Configure delivery
18. Use AI assistant
19. Build agent
20. Build automation
21. View notification
22. Manage workspace
23. Review billing
24. Create API key

Run:

- Formatting
- Linting
- Type checking
- Unit tests
- Component tests
- Accessibility tests
- End-to-end tests
- Production build

Fix failures caused by the implementation.

---

# 37. Performance Requirements

Implement:

- Route lazy loading
- Component lazy loading where valuable
- Table virtualization foundation
- Request cancellation
- Query deduplication
- Debounced search
- Efficient list rendering
- Memoized derived state where useful
- Bundle awareness
- Avoid unnecessary watchers
- Avoid unnecessary global reactivity
- Loading boundaries
- Image optimization
- Large-canvas performance considerations

Do not prematurely optimize at the expense of maintainability, but do not build obviously inefficient architecture.

---

# 38. Documentation

Create or update:

- Frontend architecture documentation
- Route registry documentation
- Design token documentation
- Component documentation
- Layout documentation
- Permission and entitlement UI rules
- Mock-service documentation
- Backend integration map
- Module-status matrix
- Testing guide
- Accessibility baseline
- Development commands
- Known limitations
- Deferred backend dependencies

For every mocked endpoint, document:

- Intended backend route
- Request contract
- Response contract
- Error cases
- Required permission
- Required organization or workspace context
- Current mock implementation location

---

# 39. Git and Change Management

Keep implementation commits focused and understandable.

Do not commit:

- Secrets
- Credentials
- Build output
- Local environment files
- Temporary files
- Generated caches

At meaningful implementation checkpoints:

1. Review the working tree.
2. Run relevant validation.
3. Create a focused commit.
4. Continue with the next batch.

Use clear commit messages such as:

- feat(ui): implement VIP application shell
- feat(ui): add shared form and data systems
- feat(connections): build Connection Studio frontend
- feat(pipelines): build Pipeline Studio frontend
- feat(data): add datasets and semantic studio
- feat(analytics): build dashboard and report studios
- feat(ai): add AI Studio and assistant
- feat(automation): implement automation frontend
- feat(admin): add administration and billing interfaces
- feat(developer): add developer portal and marketplace
- test(ui): add frontend acceptance suite

Do not push unless explicitly instructed.

---

# 40. Mandatory Implementation Order

Follow this order:

## Batch 1 — Foundation

- Repository assessment
- Design tokens
- Themes
- Shared UI
- Application shell
- Layouts
- Routing
- Permissions
- Feature flags
- Entitlements
- API and mock architecture

## Batch 2 — Shared Systems

- Forms
- Tables
- Filters
- Pagination
- Dialogs
- Drawers
- Feedback
- Loading and error states
- Settings
- Command palette
- Global search

## Batch 3 — Data Platform

- Home
- Connection Studio
- Pipeline Studio
- Dataset Studio
- Semantic Studio
- Quality
- Lineage

## Batch 4 — Analytics

- Dashboard Studio
- Dashboard viewer
- Report Studio
- Approvals
- Exports
- Scheduled-delivery interfaces

## Batch 5 — Intelligence and Automation

- Notifications
- AI Assistant
- AI Studio
- Knowledge bases
- Agent builder
- Agent runs
- Automation builder
- Automation runs

## Batch 6 — SaaS Operations

- Platform administration
- Organization administration
- Workspace administration
- Feature flags
- Governance
- Billing
- Usage
- Quotas
- Audit

## Batch 7 — Ecosystem

- Developer Portal
- API keys
- Webhooks
- Documentation
- SDK pages
- Embedding foundation
- Marketplace
- Extensions

## Batch 8 — Final Quality Gate

- Accessibility
- Responsive validation
- Browser validation
- Performance review
- Visual consistency
- End-to-end tests
- Production build
- Documentation
- Completion report

---

# 41. Definition of Done

The frontend is complete only when:

- The entire route structure exists.
- Every major module is navigable.
- Every planned module has a coherent user interface.
- Shared components are used consistently.
- Light and dark themes work.
- Desktop, laptop, tablet, and supported mobile workflows work.
- Permission-aware navigation works.
- Feature-flag and entitlement states work.
- Organization and workspace context is always visible.
- Core workflows work against typed mock services.
- Mock services can later be replaced by real APIs.
- Loading, empty, error, success, forbidden, and upgrade states exist.
- Forms are validated and accessible.
- Tables support enterprise interactions.
- Studio layouts are functional.
- Canvas foundations are usable.
- No major page is a blank placeholder.
- No major workflow is represented only by static text.
- Tests pass.
- Type checking passes.
- Linting passes.
- Production build passes.
- Documentation is updated.
- Backend integration points are documented.

---

# 42. Final Report

At completion, provide:

## Architecture

- Final frontend architecture
- Important architectural decisions
- State-management boundaries
- API integration pattern
- Mock replacement pattern

## Implementation

- Modules completed
- Routes added
- Components added
- Layouts added
- Stores added
- Composables added
- Services added
- Mock APIs added

## Quality

- Tests added
- Accessibility validation
- Responsive validation
- Type-check result
- Lint result
- Test result
- Build result

## Backend Readiness

- Required backend endpoints
- API contracts created
- Authentication dependencies
- RBAC dependencies
- Feature-flag dependencies
- Entitlement dependencies
- Background-job dependencies
- File-upload dependencies
- Streaming dependencies

## Git

- Commits created
- Commit hashes
- Final repository status

## Remaining Risks

- Incomplete areas
- Technical blockers
- Backend-dependent limitations
- Performance risks
- Accessibility risks
- Recommended next actions

---

# Final Instruction

Build a coherent enterprise product, not a collection of mock screens.

Every page must follow the same design system.

Every module must use shared architecture.

Every interaction must be realistic.

Every API-dependent feature must have a typed integration boundary.

Do not stop at visual appearance.

Build the complete VIP frontend so it is ready to be connected to the backend and evolved into a production enterprise SaaS platform.
