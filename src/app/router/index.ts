import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { usePlatformStore } from '@/shared/stores/platform'
import { hasPermission } from '@/shared/permissions/roles'
import './meta'

/* Lazy module chunks — route-level code splitting. */
const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/home' },

  // Core
  { path: '/home', name: 'home', component: () => import('@/modules/home/HomeView.vue'), meta: { title: 'Home', layout: 'app', requiresAuth: true } },
  { path: '/favorites', name: 'favorites', component: () => import('@/modules/home/FavoritesView.vue'), meta: { title: 'Favorites', layout: 'app', requiresAuth: true } },
  { path: '/activity', name: 'activity', component: () => import('@/modules/home/ActivityView.vue'), meta: { title: 'Recent Activity', layout: 'app', requiresAuth: true } },

  // Connections
  { path: '/connections', name: 'connections', component: () => import('@/modules/connections/ConnectionListView.vue'), meta: { title: 'Connections', layout: 'app', requiresAuth: true, permission: 'connection:read' } },
  { path: '/connections/catalog', name: 'connection-catalog', component: () => import('@/modules/connections/ConnectorCatalogView.vue'), meta: { title: 'Connector Catalog', layout: 'app', requiresAuth: true, permission: 'connection:read' } },
  { path: '/connections/new', name: 'connection-new', component: () => import('@/modules/connections/ConnectionWizardView.vue'), meta: { title: 'New Connection', layout: 'app', requiresAuth: true, permission: 'connection:write' } },
  { path: '/connections/:id', name: 'connection-detail', component: () => import('@/modules/connections/ConnectionDetailView.vue'), meta: { title: 'Connection', layout: 'app', requiresAuth: true, permission: 'connection:read' } },

  // Pipelines (priority studio)
  { path: '/pipelines', name: 'pipelines', component: () => import('@/modules/pipelines/PipelineListView.vue'), meta: { title: 'Pipelines', layout: 'app', requiresAuth: true, permission: 'pipeline:read', entitlement: 'pipelines' } },
  { path: '/pipelines/new', name: 'pipeline-new', component: () => import('@/modules/pipelines/PipelineStudioView.vue'), meta: { title: 'New Pipeline', layout: 'studio', requiresAuth: true, permission: 'pipeline:write', entitlement: 'pipelines', fullBleed: true } },
  { path: '/pipelines/:id', name: 'pipeline-studio', component: () => import('@/modules/pipelines/PipelineStudioView.vue'), meta: { title: 'Pipeline Studio', layout: 'studio', requiresAuth: true, permission: 'pipeline:read', entitlement: 'pipelines', fullBleed: true } },
  { path: '/pipelines/:id/runs', name: 'pipeline-runs', component: () => import('@/modules/pipelines/PipelineRunsView.vue'), meta: { title: 'Pipeline Runs', layout: 'app', requiresAuth: true, permission: 'pipeline:read' } },

  // Datasets / semantic / quality / lineage
  { path: '/datasets', name: 'datasets', component: () => import('@/modules/datasets/DatasetListView.vue'), meta: { title: 'Datasets', layout: 'app', requiresAuth: true, permission: 'dataset:read' } },
  { path: '/datasets/quality', name: 'data-quality', component: () => import('@/modules/datasets/DataQualityView.vue'), meta: { title: 'Data Quality', layout: 'app', requiresAuth: true, permission: 'dataset:read' } },
  { path: '/datasets/lineage', name: 'data-lineage', component: () => import('@/modules/datasets/DataLineageView.vue'), meta: { title: 'Data Lineage', layout: 'app', requiresAuth: true, permission: 'dataset:read' } },
  { path: '/datasets/:id', name: 'dataset-detail', component: () => import('@/modules/datasets/DatasetDetailView.vue'), meta: { title: 'Dataset', layout: 'app', requiresAuth: true, permission: 'dataset:read' } },
  { path: '/semantic', name: 'semantic', component: () => import('@/modules/semantic/SemanticListView.vue'), meta: { title: 'Semantic Models', layout: 'app', requiresAuth: true, permission: 'semantic:read' } },
  { path: '/semantic/metrics', name: 'metrics', component: () => import('@/modules/semantic/MetricsView.vue'), meta: { title: 'Metrics & KPIs', layout: 'app', requiresAuth: true, permission: 'semantic:read' } },
  { path: '/semantic/glossary', name: 'glossary', component: () => import('@/modules/semantic/GlossaryView.vue'), meta: { title: 'Business Glossary', layout: 'app', requiresAuth: true, permission: 'semantic:read' } },
  { path: '/semantic/:id', name: 'semantic-detail', component: () => import('@/modules/semantic/SemanticBuilderView.vue'), meta: { title: 'Semantic Model', layout: 'app', requiresAuth: true, permission: 'semantic:read' } },

  // Analytics (priority)
  { path: '/dashboards', name: 'dashboards', component: () => import('@/modules/dashboards/DashboardListView.vue'), meta: { title: 'Dashboards', layout: 'app', requiresAuth: true, permission: 'dashboard:read', entitlement: 'dashboards' } },
  { path: '/dashboards/templates', name: 'dashboard-templates', component: () => import('@/modules/dashboards/DashboardTemplatesView.vue'), meta: { title: 'Dashboard Templates', layout: 'app', requiresAuth: true, permission: 'dashboard:read', entitlement: 'dashboards' } },
  { path: '/dashboards/published', name: 'dashboards-published', component: () => import('@/modules/dashboards/DashboardListView.vue'), meta: { title: 'Published Dashboards', layout: 'app', requiresAuth: true, permission: 'dashboard:read', entitlement: 'dashboards' } },
  { path: '/dashboards/deliveries', name: 'dashboard-deliveries', component: () => import('@/modules/dashboards/DashboardDeliveriesView.vue'), meta: { title: 'Scheduled Deliveries', layout: 'app', requiresAuth: true, permission: 'dashboard:read', entitlement: 'dashboards' } },
  { path: '/dashboards/new', name: 'dashboard-new', component: () => import('@/modules/dashboards/DashboardStudioView.vue'), meta: { title: 'New Dashboard', layout: 'studio', requiresAuth: true, permission: 'dashboard:write', entitlement: 'dashboards', fullBleed: true } },
  { path: '/dashboards/:id/edit', name: 'dashboard-studio', component: () => import('@/modules/dashboards/DashboardStudioView.vue'), meta: { title: 'Dashboard Studio', layout: 'studio', requiresAuth: true, permission: 'dashboard:write', entitlement: 'dashboards', fullBleed: true } },
  { path: '/dashboards/:id', name: 'dashboard-viewer', component: () => import('@/modules/dashboards/DashboardViewerView.vue'), meta: { title: 'Dashboard', layout: 'app', requiresAuth: true, permission: 'dashboard:read', fullBleed: true } },

  { path: '/insights', name: 'insights', component: () => import('@/modules/insights/InsightsView.vue'), meta: { title: 'Insights', layout: 'app', requiresAuth: true, permission: 'insight:read' } },
  { path: '/explore', name: 'explore', component: () => import('@/modules/explore/ExploreView.vue'), meta: { title: 'Explore', layout: 'studio', requiresAuth: true, permission: 'dashboard:read', fullBleed: true } },

  // Reports
  { path: '/reports', name: 'reports', component: () => import('@/modules/reports/ReportListView.vue'), meta: { title: 'Reports', layout: 'app', requiresAuth: true, permission: 'report:read' } },
  { path: '/reports/new', name: 'report-new', component: () => import('@/modules/reports/ReportBuilderView.vue'), meta: { title: 'New Report', layout: 'studio', requiresAuth: true, permission: 'report:write', fullBleed: true } },
  { path: '/reports/deliveries', name: 'deliveries', component: () => import('@/modules/reports/DeliveriesView.vue'), meta: { title: 'Scheduled Deliveries', layout: 'app', requiresAuth: true, permission: 'report:read' } },
  { path: '/reports/:id', name: 'report-builder', component: () => import('@/modules/reports/ReportBuilderView.vue'), meta: { title: 'Report', layout: 'studio', requiresAuth: true, permission: 'report:read', fullBleed: true } },

  // AI
  { path: '/ai/assistant', name: 'ai-assistant', component: () => import('@/modules/ai/AssistantView.vue'), meta: { title: 'AI Assistant', layout: 'app', requiresAuth: true, permission: 'ai:use', entitlement: 'ai-assistant', fullBleed: true } },
  { path: '/ai/studio', name: 'ai-studio', component: () => import('@/modules/ai/AiStudioView.vue'), meta: { title: 'AI Studio', layout: 'app', requiresAuth: true, permission: 'ai:configure' } },
  { path: '/ai/knowledge', name: 'ai-knowledge', component: () => import('@/modules/ai/KnowledgeView.vue'), meta: { title: 'Knowledge Bases', layout: 'app', requiresAuth: true, permission: 'ai:configure' } },
  { path: '/ai/agents', name: 'ai-agents', component: () => import('@/modules/ai/AgentsView.vue'), meta: { title: 'AI Agents', layout: 'app', requiresAuth: true, permission: 'ai:configure', entitlement: 'ai-agents' } },
  { path: '/ai/agent-runs', name: 'agent-runs', component: () => import('@/modules/ai/AgentRunsView.vue'), meta: { title: 'Agent Runs', layout: 'app', requiresAuth: true, permission: 'ai:configure', entitlement: 'ai-agents' } },

  // Automation
  { path: '/automation', name: 'automation', component: () => import('@/modules/automation/AutomationListView.vue'), meta: { title: 'Automations', layout: 'app', requiresAuth: true, permission: 'automation:read', entitlement: 'automation' } },
  { path: '/automation/new', name: 'automation-new', component: () => import('@/modules/automation/AutomationBuilderView.vue'), meta: { title: 'New Automation', layout: 'studio', requiresAuth: true, permission: 'automation:write', entitlement: 'automation', fullBleed: true } },
  { path: '/automation/runs', name: 'automation-runs', component: () => import('@/modules/automation/AutomationRunsView.vue'), meta: { title: 'Automation Runs', layout: 'app', requiresAuth: true, permission: 'automation:read' } },
  { path: '/automation/approvals', name: 'approvals', component: () => import('@/modules/automation/ApprovalsView.vue'), meta: { title: 'Approvals', layout: 'app', requiresAuth: true, permission: 'automation:read' } },
  { path: '/automation/:id', name: 'automation-builder', component: () => import('@/modules/automation/AutomationBuilderView.vue'), meta: { title: 'Automation', layout: 'studio', requiresAuth: true, permission: 'automation:read', fullBleed: true } },

  // Operations
  { path: '/notifications', name: 'notifications', component: () => import('@/modules/operations/NotificationsView.vue'), meta: { title: 'Notifications', layout: 'app', requiresAuth: true } },
  { path: '/operations/activity', name: 'op-activity', component: () => import('@/modules/operations/ActivityCenterView.vue'), meta: { title: 'Activity Center', layout: 'app', requiresAuth: true } },
  { path: '/audit', name: 'audit', component: () => import('@/modules/operations/AuditCenterView.vue'), meta: { title: 'Audit Center', layout: 'app', requiresAuth: true, permission: 'audit:read' } },
  { path: '/usage', name: 'usage', component: () => import('@/modules/operations/UsageView.vue'), meta: { title: 'Usage', layout: 'app', requiresAuth: true, permission: 'usage:read' } },

  // Platform
  { path: '/marketplace', name: 'marketplace', component: () => import('@/modules/marketplace/MarketplaceView.vue'), meta: { title: 'Marketplace', layout: 'app', requiresAuth: true, permission: 'marketplace:read', entitlement: 'marketplace' } },
  { path: '/marketplace/:id', name: 'marketplace-detail', component: () => import('@/modules/marketplace/ExtensionDetailView.vue'), meta: { title: 'Extension', layout: 'app', requiresAuth: true, permission: 'marketplace:read' } },
  { path: '/developer', name: 'developer', component: () => import('@/modules/developer/DeveloperPortalView.vue'), meta: { title: 'Developer Portal', layout: 'app', requiresAuth: true, permission: 'developer:read', entitlement: 'developer-api' } },

  // Administration
  { path: '/admin/platform', name: 'admin-platform', component: () => import('@/modules/admin/PlatformAdminView.vue'), meta: { title: 'Platform Administration', layout: 'app', requiresAuth: true, permission: 'admin:platform' } },
  { path: '/admin/organization', name: 'admin-org', component: () => import('@/modules/admin/OrgAdminView.vue'), meta: { title: 'Organization Administration', layout: 'app', requiresAuth: true, permission: 'admin:org' } },
  { path: '/admin/workspace', name: 'admin-workspace', component: () => import('@/modules/admin/WorkspaceAdminView.vue'), meta: { title: 'Workspace Administration', layout: 'app', requiresAuth: true, permission: 'admin:workspace' } },
  { path: '/admin/members', name: 'admin-members', component: () => import('@/modules/admin/MembersView.vue'), meta: { title: 'Members & Roles', layout: 'app', requiresAuth: true, permission: 'admin:org' } },
  { path: '/admin/feature-flags', name: 'admin-flags', component: () => import('@/modules/admin/FeatureFlagsView.vue'), meta: { title: 'Feature Flags', layout: 'app', requiresAuth: true, permission: 'featureflag:read' } },
  { path: '/admin/governance', name: 'admin-governance', component: () => import('@/modules/admin/GovernanceView.vue'), meta: { title: 'Governance', layout: 'app', requiresAuth: true, permission: 'governance:read' } },
  { path: '/billing', name: 'billing', component: () => import('@/modules/billing/BillingView.vue'), meta: { title: 'Billing', layout: 'app', requiresAuth: true, permission: 'billing:read' } },

  // Settings
  { path: '/settings/:section?', name: 'settings', component: () => import('@/modules/settings/SettingsView.vue'), meta: { title: 'Settings', layout: 'settings', requiresAuth: true } },

  // Errors
  { path: '/forbidden', name: 'forbidden', component: () => import('@/modules/errors/ForbiddenView.vue'), meta: { title: 'Forbidden', layout: 'error' } },
  { path: '/upgrade', name: 'upgrade', component: () => import('@/modules/errors/UpgradeView.vue'), meta: { title: 'Upgrade Required', layout: 'error' } },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/modules/errors/NotFoundView.vue'), meta: { title: 'Not Found', layout: 'error' } },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
})

router.beforeEach((to) => {
  const platform = usePlatformStore()

  if (to.meta.permission && !hasPermission(platform.permissions, to.meta.permission)) {
    return { name: 'forbidden', query: { from: to.fullPath } }
  }
  if (to.meta.entitlement && !platform.entitled(to.meta.entitlement)) {
    return { name: 'upgrade', query: { feature: to.meta.entitlement, from: to.fullPath } }
  }
  if (to.meta.featureFlag && !platform.flagEnabled(to.meta.featureFlag)) {
    return { name: 'not-found' }
  }
  return true
})

router.afterEach((to) => {
  const base = 'VIP — Veltrix Intelligence Platform'
  document.title = to.meta.title ? `${to.meta.title} · ${base}` : base
})
