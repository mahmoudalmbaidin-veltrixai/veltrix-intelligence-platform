/**
 * Central navigation registry. Drives the sidebar, breadcrumbs, command
 * palette and route search. Each item is permission / entitlement /
 * feature-flag aware so the shell hides what the current context can't use.
 */
import type { EntitlementKey, FeatureFlagKey, Permission } from '@/shared/types/identity'
import { config, type ApiMode } from '@/shared/config/env'
import { isProductionGatedFeature } from '@/app/featureAvailability'

export interface NavItem {
  label: string
  to: string
  icon: string
  /** One-line summary shown in collapsed-sidebar tooltips. */
  description?: string
  /** Human-readable keyboard shortcut shown in tooltips, when one exists. */
  shortcut?: string
  permission?: Permission
  entitlement?: EntitlementKey
  featureFlag?: FeatureFlagKey
  keywords?: string[]
  adminOnly?: boolean
  /** Cross-tenant platform super-admin only. */
  platformAdminOnly?: boolean
  /** Incomplete preview surface: available only in explicitly permitted development mock mode. */
  developmentMockOnly?: boolean
}

export interface NavGroup {
  key: string
  label: string
  items: NavItem[]
}

export interface NavigationAccess {
  isPlatformAdmin: boolean
  can(permission: Permission): boolean
  entitled(entitlement: EntitlementKey): boolean
  flagEnabled(feature: FeatureFlagKey): boolean
}

export function canExposeNavigationItem(
  item: NavItem,
  access: NavigationAccess,
  apiMode: ApiMode = config.apiMode,
): boolean {
  if (item.developmentMockOnly && apiMode !== 'mock') return false
  // Centralized V1 product gate: unfinished modules are hidden in production
  // regardless of role/entitlement (a super admin cannot reveal them either).
  if (isProductionGatedFeature({ entitlement: item.entitlement, path: item.to }, apiMode)) {
    return false
  }
  if (item.platformAdminOnly && !access.isPlatformAdmin) return false
  if (item.permission && !access.can(item.permission)) return false
  if (item.entitlement && !access.entitled(item.entitlement)) return false
  if (item.featureFlag && !access.flagEnabled(item.featureFlag)) return false
  return true
}

export const NAV_GROUPS: NavGroup[] = [
  {
    key: 'core',
    label: 'Core',
    items: [
      {
        label: 'Home',
        to: '/home',
        icon: 'home',
        description: 'Your personalized overview and starting point.',
        keywords: ['dashboard', 'start', 'overview'],
      },
      {
        label: 'Favorites',
        to: '/favorites',
        icon: 'star',
        description: 'Quick access to items you have starred.',
      },
      {
        label: 'Recent activity',
        to: '/activity',
        icon: 'clock',
        description: 'Recently viewed and edited resources.',
        keywords: ['history'],
      },
    ],
  },
  {
    key: 'data',
    label: 'Data',
    items: [
      {
        label: 'Connections',
        to: '/connections',
        icon: 'plug',
        description: 'Manage enterprise data connections and credentials.',
        permission: 'connection.read',
        entitlement: 'connection_studio',
        featureFlag: 'connection_studio',
        keywords: ['source', 'database', 'connector'],
      },
      {
        label: 'Pipelines',
        to: '/pipelines',
        icon: 'workflow',
        description: 'Build and orchestrate visual ETL data pipelines.',
        // Entitlement-only: users with resource-ACL grants (but no broad
        // pipeline.read) can reach their shared pipelines via the filtered list.
        entitlement: 'pipeline_studio',
        keywords: ['etl', 'flow', 'transform', 'alteryx'],
      },
      {
        label: 'Datasets',
        to: '/datasets',
        icon: 'database',
        description: 'Browse governed tables and prepared datasets.',
        permission: 'dataset.read',
        keywords: ['tables', 'data'],
      },
      {
        label: 'Semantic Models',
        to: '/semantic',
        icon: 'layers',
        description: 'Define reusable business models and relationships.',
        permission: 'dataset.read',
        keywords: ['model', 'metrics'],
      },
      {
        label: 'Metrics & KPIs',
        to: '/semantic/metrics',
        icon: 'target',
        description: 'Central catalog of certified metrics and KPIs.',
        permission: 'dataset.read',
      },
      {
        label: 'Data Quality',
        to: '/datasets/quality',
        icon: 'gauge',
        description: 'Monitor freshness, completeness and validation rules.',
        permission: 'dataset.read',
      },
      {
        label: 'Data Lineage',
        to: '/datasets/lineage',
        icon: 'lineage',
        description: 'Trace how data flows across sources and outputs.',
        permission: 'dataset.read',
      },
    ],
  },
  {
    key: 'analytics',
    label: 'Analytics',
    items: [
      {
        label: 'Dashboards',
        to: '/dashboards',
        icon: 'chart',
        description: 'Interactive BI dashboards across your workspace.',
        permission: 'dashboard.read',
        entitlement: 'dashboard_studio',
        keywords: ['bi', 'visual', 'powerbi'],
      },
      {
        label: 'Dashboard Studio',
        to: '/dashboards/new',
        icon: 'grid',
        description: 'Author dashboards on an editable widget canvas.',
        permission: 'dashboard.create',
        entitlement: 'dashboard_studio',
        keywords: ['build', 'author', 'create', 'widgets', 'canvas'],
      },
      {
        label: 'Dashboard Templates',
        to: '/dashboards/templates',
        icon: 'layers',
        description: 'Start faster from curated, pre-built layouts.',
        permission: 'dashboard.read',
        entitlement: 'dashboard_studio',
        keywords: ['starter', 'gallery'],
      },
      {
        label: 'Published Dashboards',
        to: '/dashboards/published',
        icon: 'eye',
        description: 'Live dashboards shared with your organization.',
        permission: 'dashboard.read',
        entitlement: 'dashboard_studio',
        keywords: ['live', 'shared'],
      },
      {
        label: 'Insights',
        to: '/insights',
        icon: 'sparkles',
        description: 'AI-detected trends, anomalies and highlights.',
        permission: 'dashboard.read',
        entitlement: 'insights',
        keywords: ['ai', 'trend', 'anomaly', 'analyze'],
      },
      {
        label: 'Explore',
        to: '/explore',
        icon: 'trendUp',
        description: 'Ad-hoc analysis and self-service discovery.',
        permission: 'dashboard.read',
        keywords: ['adhoc', 'analysis', 'discover'],
      },
      {
        label: 'Reports',
        to: '/reports',
        icon: 'report',
        description: 'Paginated, print-ready operational reports.',
        permission: 'report.read',
        entitlement: 'report_studio',
      },
      {
        label: 'Scheduled Deliveries',
        to: '/dashboards/deliveries',
        icon: 'calendar',
        description: 'Email dashboards to recipients on a schedule.',
        permission: 'dashboard.read',
        entitlement: 'dashboard_studio',
        keywords: ['email', 'schedule', 'subscribe'],
      },
    ],
  },
  {
    key: 'intelligence',
    label: 'Intelligence',
    items: [
      {
        label: 'AI Assistant',
        to: '/ai/assistant',
        icon: 'bot',
        description: 'Ask questions and generate analytics with AI.',
        permission: 'ai.use',
        entitlement: 'ai_studio',
        featureFlag: 'ai_studio',
        developmentMockOnly: true,
      },
      {
        label: 'AI Studio',
        to: '/ai/studio',
        icon: 'brain',
        description: 'Configure models, prompts and AI capabilities.',
        permission: 'ai.configure',
        entitlement: 'ai_studio',
        featureFlag: 'ai_studio',
        developmentMockOnly: true,
      },
      {
        label: 'Knowledge Bases',
        to: '/ai/knowledge',
        icon: 'book',
        description: 'Curate grounded content sources for AI answers.',
        permission: 'ai.configure',
        entitlement: 'ai_studio',
        featureFlag: 'ai_studio',
        developmentMockOnly: true,
      },
      {
        label: 'AI Agents',
        to: '/ai/agents',
        icon: 'sparkles',
        description: 'Automated agents that act on your data.',
        permission: 'ai.configure',
        entitlement: 'ai_studio',
        featureFlag: 'ai_studio',
        developmentMockOnly: true,
      },
      {
        label: 'Agent Runs',
        to: '/ai/agent-runs',
        icon: 'run',
        description: 'History and status of AI agent executions.',
        permission: 'ai.configure',
        entitlement: 'ai_studio',
        featureFlag: 'ai_studio',
        developmentMockOnly: true,
      },
    ],
  },
  {
    key: 'automation',
    label: 'Automation',
    items: [
      {
        label: 'Automations',
        to: '/automation',
        icon: 'workflow',
        description: 'Design event-driven workflows and triggers.',
        permission: 'automation.read',
        entitlement: 'automation',
      },
      {
        label: 'Automation Runs',
        to: '/automation/runs',
        icon: 'run',
        description: 'Execution history for your automations.',
        permission: 'automation.read',
        entitlement: 'automation',
      },
      {
        label: 'Approvals',
        to: '/automation/approvals',
        icon: 'check',
        description: 'Review and action pending approval requests.',
        permission: 'automation.read',
        entitlement: 'automation',
      },
    ],
  },
  {
    key: 'operations',
    label: 'Operations',
    items: [
      {
        label: 'Notifications',
        to: '/notifications',
        icon: 'bell',
        description: 'Platform alerts, mentions and system messages.',
        permission: 'notification.read',
      },
      {
        label: 'Activity',
        to: '/operations/activity',
        icon: 'activity',
        description: 'Operational event stream across the platform.',
      },
      {
        label: 'Audit Center',
        to: '/audit',
        icon: 'audit',
        description: 'Immutable audit log of security-relevant actions.',
        permission: 'audit.read',
      },
      {
        label: 'Usage',
        to: '/usage',
        icon: 'usage',
        description: 'Consumption metrics and capacity utilization.',
        permission: 'governance.read',
      },
    ],
  },
  {
    key: 'platform',
    label: 'Platform',
    items: [
      {
        label: 'Marketplace',
        to: '/marketplace',
        icon: 'store',
        description: 'Discover and install connectors and extensions.',
        permission: 'workspace.read',
        entitlement: 'marketplace',
      },
      {
        label: 'Developer Portal',
        to: '/developer',
        icon: 'code',
        description: 'APIs, SDKs and developer documentation.',
        permission: 'developer.read',
        entitlement: 'developer_api',
      },
    ],
  },
  {
    key: 'administration',
    label: 'Administration',
    items: [
      {
        label: 'Platform Admin',
        to: '/platform',
        icon: 'building',
        description: 'Cross-tenant operator console: all organizations, workspaces and users.',
        keywords: ['super admin', 'saas', 'tenants', 'operator'],
        platformAdminOnly: true,
      },
      {
        label: 'Organization Admin',
        to: '/admin/organization',
        icon: 'building',
        description: 'Manage organization settings and policies.',
        permission: 'governance.read',
        adminOnly: true,
      },
      {
        label: 'Workspace Admin',
        to: '/admin/workspace',
        icon: 'settings',
        description: 'Configure this workspace and its resources.',
        permission: 'workspace.update',
        adminOnly: true,
      },
      {
        label: 'Members & Roles',
        to: '/admin/members',
        icon: 'users',
        description: 'Invite members and assign access roles.',
        permission: 'governance.read',
        adminOnly: true,
      },
      {
        label: 'Roles',
        to: '/admin/roles',
        icon: 'shield',
        description: 'Create custom roles and assign them to users and groups.',
        keywords: ['roles', 'rbac', 'permissions', 'custom role', 'assignments'],
        permission: 'role.read',
        adminOnly: true,
      },
      {
        label: 'Groups & Teams',
        to: '/admin/groups',
        icon: 'users',
        description: 'Create teams and manage their membership and resource access.',
        keywords: ['teams', 'groups', 'membership'],
        permission: 'group.read',
        adminOnly: true,
      },
      {
        label: 'Access Control',
        to: '/admin/access',
        icon: 'shield',
        description: 'Share resources, inspect effective permissions and simulate access.',
        keywords: ['permissions', 'sharing', 'acl', 'effective access', 'simulate'],
        permission: 'resource.permissions.read',
        adminOnly: true,
      },
      {
        label: 'Billing',
        to: '/billing',
        icon: 'card',
        description: 'Plans, invoices and payment methods.',
        permission: 'billing.read',
        entitlement: 'billing',
        adminOnly: true,
      },
      {
        label: 'Feature Flags',
        to: '/admin/feature-flags',
        icon: 'flag',
        description: 'Toggle capabilities and staged rollouts.',
        permission: 'governance.read',
        adminOnly: true,
      },
      {
        label: 'Governance',
        to: '/admin/governance',
        icon: 'shield',
        description: 'Data policies, compliance and access reviews.',
        permission: 'governance.read',
        adminOnly: true,
      },
    ],
  },
  {
    key: 'settings',
    label: 'Settings',
    items: [
      {
        // Personal account only. Organization and workspace administration live
        // in the dedicated Admin navigation, never duplicated inside Settings.
        label: 'Settings',
        to: '/settings/profile',
        icon: 'settings',
        description: 'Your profile, security, preferences and sessions.',
      },
    ],
  },
]

export const QUICK_CREATE: NavItem[] = [
  { label: 'New Connection', to: '/connections/new', icon: 'plug', permission: 'connection.create' },
  { label: 'New Pipeline', to: '/pipelines/new', icon: 'workflow', permission: 'pipeline.create' },
  { label: 'New Dashboard', to: '/dashboards/new', icon: 'chart', permission: 'dashboard.create' },
  {
    label: 'New Report',
    to: '/reports/new',
    icon: 'report',
    permission: 'report.create',
    entitlement: 'report_studio',
  },
  {
    label: 'New Automation',
    to: '/automation/new',
    icon: 'workflow',
    permission: 'automation.write',
    entitlement: 'automation',
  },
]
