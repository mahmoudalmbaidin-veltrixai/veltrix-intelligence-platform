/**
 * Central navigation registry. Drives the sidebar, breadcrumbs, command
 * palette and route search. Each item is permission / entitlement /
 * feature-flag aware so the shell hides what the current context can't use.
 */
import type { EntitlementKey, FeatureFlagKey, Permission } from '@/shared/types/identity'

export interface NavItem {
  label: string
  to: string
  icon: string
  permission?: Permission
  entitlement?: EntitlementKey
  featureFlag?: FeatureFlagKey
  keywords?: string[]
  adminOnly?: boolean
}

export interface NavGroup {
  key: string
  label: string
  items: NavItem[]
}

export const NAV_GROUPS: NavGroup[] = [
  {
    key: 'core',
    label: 'Core',
    items: [
      { label: 'Home', to: '/home', icon: 'home', keywords: ['dashboard', 'start', 'overview'] },
      { label: 'Favorites', to: '/favorites', icon: 'star' },
      { label: 'Recent activity', to: '/activity', icon: 'clock', keywords: ['history'] },
    ],
  },
  {
    key: 'data',
    label: 'Data',
    items: [
      { label: 'Connections', to: '/connections', icon: 'plug', permission: 'connection:read', keywords: ['source', 'database', 'connector'] },
      { label: 'Pipelines', to: '/pipelines', icon: 'workflow', permission: 'pipeline:read', entitlement: 'pipelines', keywords: ['etl', 'flow', 'transform', 'alteryx'] },
      { label: 'Datasets', to: '/datasets', icon: 'database', permission: 'dataset:read', keywords: ['tables', 'data'] },
      { label: 'Semantic Models', to: '/semantic', icon: 'layers', permission: 'semantic:read', keywords: ['model', 'metrics'] },
      { label: 'Metrics & KPIs', to: '/semantic/metrics', icon: 'target', permission: 'semantic:read' },
      { label: 'Data Quality', to: '/datasets/quality', icon: 'gauge', permission: 'dataset:read' },
      { label: 'Data Lineage', to: '/datasets/lineage', icon: 'lineage', permission: 'dataset:read' },
    ],
  },
  {
    key: 'analytics',
    label: 'Analytics',
    items: [
      { label: 'Dashboards', to: '/dashboards', icon: 'chart', permission: 'dashboard:read', entitlement: 'dashboards', keywords: ['bi', 'visual', 'powerbi'] },
      { label: 'Dashboard Studio', to: '/dashboards/new', icon: 'grid', permission: 'dashboard:write', entitlement: 'dashboards', keywords: ['build', 'author', 'create', 'widgets', 'canvas'] },
      { label: 'Dashboard Templates', to: '/dashboards/templates', icon: 'layers', permission: 'dashboard:read', entitlement: 'dashboards', keywords: ['starter', 'gallery'] },
      { label: 'Published Dashboards', to: '/dashboards/published', icon: 'eye', permission: 'dashboard:read', entitlement: 'dashboards', keywords: ['live', 'shared'] },
      { label: 'Insights', to: '/insights', icon: 'sparkles', permission: 'insight:read', keywords: ['ai', 'trend', 'anomaly', 'analyze'] },
      { label: 'Explore', to: '/explore', icon: 'trendUp', permission: 'dashboard:read', keywords: ['adhoc', 'analysis', 'discover'] },
      { label: 'Reports', to: '/reports', icon: 'report', permission: 'report:read' },
      { label: 'Scheduled Deliveries', to: '/dashboards/deliveries', icon: 'calendar', permission: 'dashboard:read', entitlement: 'dashboards', keywords: ['email', 'schedule', 'subscribe'] },
    ],
  },
  {
    key: 'intelligence',
    label: 'Intelligence',
    items: [
      { label: 'AI Assistant', to: '/ai/assistant', icon: 'bot', permission: 'ai:use', entitlement: 'ai-assistant' },
      { label: 'AI Studio', to: '/ai/studio', icon: 'brain', permission: 'ai:configure' },
      { label: 'Knowledge Bases', to: '/ai/knowledge', icon: 'book', permission: 'ai:configure' },
      { label: 'AI Agents', to: '/ai/agents', icon: 'sparkles', permission: 'ai:configure', entitlement: 'ai-agents', featureFlag: 'ai-agents-beta' },
      { label: 'Agent Runs', to: '/ai/agent-runs', icon: 'run', permission: 'ai:configure', entitlement: 'ai-agents' },
    ],
  },
  {
    key: 'automation',
    label: 'Automation',
    items: [
      { label: 'Automations', to: '/automation', icon: 'workflow', permission: 'automation:read', entitlement: 'automation' },
      { label: 'Automation Runs', to: '/automation/runs', icon: 'run', permission: 'automation:read', entitlement: 'automation' },
      { label: 'Approvals', to: '/automation/approvals', icon: 'check', permission: 'automation:read' },
    ],
  },
  {
    key: 'operations',
    label: 'Operations',
    items: [
      { label: 'Notifications', to: '/notifications', icon: 'bell', permission: 'notification:read' },
      { label: 'Activity', to: '/operations/activity', icon: 'activity' },
      { label: 'Audit Center', to: '/audit', icon: 'audit', permission: 'audit:read' },
      { label: 'Usage', to: '/usage', icon: 'usage', permission: 'usage:read' },
    ],
  },
  {
    key: 'platform',
    label: 'Platform',
    items: [
      { label: 'Marketplace', to: '/marketplace', icon: 'store', permission: 'marketplace:read', entitlement: 'marketplace' },
      { label: 'Developer Portal', to: '/developer', icon: 'code', permission: 'developer:read', entitlement: 'developer-api' },
    ],
  },
  {
    key: 'administration',
    label: 'Administration',
    items: [
      { label: 'Platform Admin', to: '/admin/platform', icon: 'building', permission: 'admin:platform', adminOnly: true },
      { label: 'Organization Admin', to: '/admin/organization', icon: 'building', permission: 'admin:org', adminOnly: true },
      { label: 'Workspace Admin', to: '/admin/workspace', icon: 'settings', permission: 'admin:workspace', adminOnly: true },
      { label: 'Members & Roles', to: '/admin/members', icon: 'users', permission: 'admin:org', adminOnly: true },
      { label: 'Billing', to: '/billing', icon: 'card', permission: 'billing:read', adminOnly: true },
      { label: 'Feature Flags', to: '/admin/feature-flags', icon: 'flag', permission: 'featureflag:read', adminOnly: true },
      { label: 'Governance', to: '/admin/governance', icon: 'shield', permission: 'governance:read', adminOnly: true },
    ],
  },
  {
    key: 'settings',
    label: 'Settings',
    items: [
      { label: 'Personal Settings', to: '/settings/personal', icon: 'settings' },
      { label: 'Workspace Settings', to: '/settings/workspace', icon: 'settings', permission: 'admin:workspace' },
      { label: 'Organization Settings', to: '/settings/organization', icon: 'building', permission: 'admin:org' },
      { label: 'Developer Settings', to: '/settings/developer', icon: 'code', permission: 'developer:read' },
      { label: 'Security', to: '/settings/security', icon: 'lock' },
    ],
  },
]

export const QUICK_CREATE: NavItem[] = [
  { label: 'New Connection', to: '/connections/new', icon: 'plug', permission: 'connection:write' },
  { label: 'New Pipeline', to: '/pipelines/new', icon: 'workflow', permission: 'pipeline:write' },
  { label: 'New Dashboard', to: '/dashboards/new', icon: 'chart', permission: 'dashboard:write' },
  { label: 'New Report', to: '/reports/new', icon: 'report', permission: 'report:write' },
  { label: 'New Automation', to: '/automation/new', icon: 'workflow', permission: 'automation:write' },
]
