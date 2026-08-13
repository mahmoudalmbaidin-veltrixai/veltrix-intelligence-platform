import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { usePlatformStore } from '@/shared/stores/platform'
import { useAuthStore } from '@/shared/stores/auth'
import { useAuthorizationStore } from '@/shared/stores/authorization'
import { config } from '@/shared/config/env'
import './meta'

/* Lazy module chunks â€” route-level code splitting. */
const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/home' },

  // Auth (guest-only)
  {
    path: '/login',
    name: 'login',
    component: () => import('@/modules/auth/LoginView.vue'),
    meta: { title: 'Sign in', layout: 'blank', publicOnly: true },
  },
  {
    path: '/forgot-password',
    name: 'forgot-password',
    component: () => import('@/modules/auth/ForgotPasswordView.vue'),
    meta: { title: 'Forgot password', layout: 'blank', publicOnly: true },
  },
  {
    path: '/reset-password',
    name: 'reset-password',
    component: () => import('@/modules/auth/ResetPasswordView.vue'),
    meta: { title: 'Reset password', layout: 'blank', publicOnly: true },
  },
  {
    path: '/force-password-change',
    name: 'force-password-change',
    component: () => import('@/modules/auth/ForcePasswordChangeView.vue'),
    meta: { title: 'Change your password', layout: 'blank', requiresAuth: true },
  },

  // Core
  {
    path: '/home',
    name: 'home',
    component: () => import('@/modules/home/HomeView.vue'),
    meta: {
      title: 'Home',
      layout: 'app',
      requiresAuth: true,
      requiresOrganization: false,
      requiresWorkspace: false,
    },
  },
  {
    path: '/platform',
    name: 'platform-admin',
    component: () => import('@/modules/platform/PlatformConsoleView.vue'),
    meta: {
      title: 'Platform Administration',
      layout: 'app',
      requiresAuth: true,
      requiresOrganization: false,
      requiresWorkspace: false,
      requiresPlatformAdmin: true,
    },
  },
  {
    path: '/favorites',
    name: 'favorites',
    component: () => import('@/modules/home/FavoritesView.vue'),
    meta: { title: 'Favorites', layout: 'app', requiresAuth: true },
  },
  {
    path: '/activity',
    name: 'activity',
    component: () => import('@/modules/home/ActivityView.vue'),
    meta: { title: 'Recent Activity', layout: 'app', requiresAuth: true },
  },

  // Connections
  {
    path: '/connections',
    name: 'connections',
    component: () => import('@/modules/connections/ConnectionListView.vue'),
    meta: {
      title: 'Connections',
      layout: 'app',
      requiresAuth: true,
      permission: 'connection.read',
      featureFlag: 'connection_studio',
      entitlement: 'connection_studio',
    },
  },
  {
    path: '/connections/catalog',
    name: 'connection-catalog',
    component: () => import('@/modules/connections/ConnectorCatalogView.vue'),
    meta: {
      title: 'Connector Catalog',
      layout: 'app',
      requiresAuth: true,
      permission: 'connection.types.read',
      featureFlag: 'connection_studio',
      entitlement: 'connection_studio',
    },
  },
  {
    path: '/connections/new',
    name: 'connection-new',
    component: () => import('@/modules/connections/ConnectionWizardView.vue'),
    meta: {
      title: 'New Connection',
      layout: 'app',
      requiresAuth: true,
      permission: 'connection.create',
      featureFlag: 'connection_studio',
      entitlement: 'connection_studio',
    },
  },
  {
    path: '/connections/:id',
    name: 'connection-detail',
    component: () => import('@/modules/connections/ConnectionDetailView.vue'),
    meta: {
      title: 'Connection',
      layout: 'app',
      requiresAuth: true,
      permission: 'connection.read',
      featureFlag: 'connection_studio',
      entitlement: 'connection_studio',
    },
  },

  // Pipelines (priority studio)
  {
    path: '/pipelines',
    name: 'pipelines',
    component: () => import('@/modules/pipelines/PipelineListView.vue'),
    meta: {
      // Entitlement-only: the backend list is visibility-filtered, so a user with
      // only resource-ACL grants (no broad pipeline.read) still sees exactly the
      // pipelines shared with them.
      title: 'Pipelines',
      layout: 'app',
      requiresAuth: true,
      entitlement: 'pipeline_studio',
    },
  },
  {
    path: '/pipelines/new',
    name: 'pipeline-new',
    component: () => import('@/modules/pipelines/PipelineStudioView.vue'),
    meta: {
      title: 'New Pipeline',
      layout: 'studio',
      requiresAuth: true,
      permission: 'pipeline.create',
      entitlement: 'pipeline_studio',
      fullBleed: true,
    },
  },
  {
    path: '/pipelines/:id',
    name: 'pipeline-studio',
    component: () => import('@/modules/pipelines/PipelineStudioView.vue'),
    meta: {
      title: 'Pipeline Studio',
      layout: 'studio',
      requiresAuth: true,
      // No broad-permission gate here: access to a specific pipeline is decided
      // per-resource by the backend (role, ownership, or a resource ACL grant),
      // so a shared user without `pipeline.read` can still open a pipeline they
      // were granted. The entitlement gates the capability; the studio shows a
      // forbidden state if the backend denies the load.
      entitlement: 'pipeline_studio',
      fullBleed: true,
    },
  },
  {
    path: '/pipelines/:id/runs',
    name: 'pipeline-runs',
    component: () => import('@/modules/pipelines/PipelineRunsView.vue'),
    // Per-resource: a viewer-level ACL grant confers run history, so gate on the
    // entitlement and let the backend authorize the specific pipeline.
    meta: { title: 'Pipeline Runs', layout: 'app', requiresAuth: true, entitlement: 'pipeline_studio' },
  },
  {
    path: '/pipelines/:id/schedules',
    name: 'pipeline-schedules',
    component: () => import('@/modules/pipelines/PipelineSchedulesView.vue'),
    // Per-resource: operator-level access is enforced by the backend; the
    // entitlement gates the capability.
    meta: {
      title: 'Pipeline Schedules',
      layout: 'app',
      requiresAuth: true,
      entitlement: 'pipeline_studio',
    },
  },

  // Datasets / semantic / quality / lineage
  {
    path: '/datasets',
    name: 'datasets',
    component: () => import('@/modules/datasets/DatasetListView.vue'),
    meta: { title: 'Datasets', layout: 'app', requiresAuth: true, permission: 'dataset.read' },
  },
  {
    path: '/datasets/quality',
    name: 'data-quality',
    component: () => import('@/modules/datasets/DataQualityView.vue'),
    meta: { title: 'Data Quality', layout: 'app', requiresAuth: true, permission: 'dataset.read' },
  },
  {
    path: '/datasets/lineage',
    name: 'data-lineage',
    component: () => import('@/modules/datasets/DataLineageView.vue'),
    meta: { title: 'Data Lineage', layout: 'app', requiresAuth: true, permission: 'dataset.read' },
  },
  {
    path: '/datasets/:id',
    name: 'dataset-detail',
    component: () => import('@/modules/datasets/DatasetDetailView.vue'),
    meta: { title: 'Dataset', layout: 'app', requiresAuth: true, permission: 'dataset.read' },
  },
  {
    path: '/semantic',
    name: 'semantic',
    component: () => import('@/modules/semantic/SemanticListView.vue'),
    meta: { title: 'Semantic Models', layout: 'app', requiresAuth: true, permission: 'semantic_model.read' },
  },
  {
    path: '/semantic/metrics',
    name: 'metrics',
    component: () => import('@/modules/semantic/MetricsView.vue'),
    meta: { title: 'Metrics & KPIs', layout: 'app', requiresAuth: true, permission: 'semantic_model.read' },
  },
  {
    path: '/semantic/glossary',
    name: 'glossary',
    component: () => import('@/modules/semantic/GlossaryView.vue'),
    meta: { title: 'Business Glossary', layout: 'app', requiresAuth: true, permission: 'glossary.read' },
  },
  {
    path: '/semantic/:id',
    name: 'semantic-detail',
    component: () => import('@/modules/semantic/SemanticBuilderView.vue'),
    meta: { title: 'Semantic Model', layout: 'app', requiresAuth: true, permission: 'semantic_model.read' },
  },

  // Analytics (priority)
  {
    path: '/dashboards',
    name: 'dashboards',
    component: () => import('@/modules/dashboards/DashboardListView.vue'),
    meta: {
      title: 'Dashboards',
      layout: 'app',
      requiresAuth: true,
      permission: 'dashboard.read',
      entitlement: 'dashboard_studio',
    },
  },
  {
    path: '/dashboards/templates',
    name: 'dashboard-templates',
    component: () => import('@/modules/dashboards/DashboardTemplatesView.vue'),
    meta: {
      title: 'Dashboard Templates',
      layout: 'app',
      requiresAuth: true,
      permission: 'dashboard.read',
      entitlement: 'dashboard_studio',
    },
  },
  {
    path: '/dashboards/published',
    name: 'dashboards-published',
    component: () => import('@/modules/dashboards/DashboardListView.vue'),
    meta: {
      title: 'Published Dashboards',
      layout: 'app',
      requiresAuth: true,
      permission: 'dashboard.read',
      entitlement: 'dashboard_studio',
    },
  },
  {
    path: '/dashboards/deliveries',
    name: 'dashboard-deliveries',
    component: () => import('@/modules/dashboards/DashboardDeliveriesView.vue'),
    meta: {
      title: 'Scheduled Deliveries',
      layout: 'app',
      requiresAuth: true,
      permission: 'dashboard.read',
      entitlement: 'dashboard_studio',
    },
  },
  {
    path: '/dashboards/new',
    name: 'dashboard-new',
    component: () => import('@/modules/dashboards/DashboardStudioView.vue'),
    meta: {
      title: 'New Dashboard',
      layout: 'studio',
      requiresAuth: true,
      permission: 'dashboard.create',
      entitlement: 'dashboard_studio',
      fullBleed: true,
    },
  },
  {
    path: '/dashboards/:id/edit',
    name: 'dashboard-studio',
    component: () => import('@/modules/dashboards/DashboardStudioView.vue'),
    meta: {
      title: 'Dashboard Studio',
      layout: 'studio',
      requiresAuth: true,
      permission: 'dashboard.create',
      entitlement: 'dashboard_studio',
      fullBleed: true,
    },
  },
  {
    path: '/dashboards/:id',
    name: 'dashboard-viewer',
    component: () => import('@/modules/dashboards/DashboardViewerView.vue'),
    meta: { title: 'Dashboard', layout: 'app', requiresAuth: true, permission: 'dashboard.read', fullBleed: true },
  },

  {
    path: '/insights',
    name: 'insights',
    component: () => import('@/modules/insights/InsightsView.vue'),
    meta: {
      title: 'Insights',
      layout: 'app',
      requiresAuth: true,
      permission: 'dashboard.read',
      entitlement: 'insights',
    },
  },
  {
    path: '/explore',
    name: 'explore',
    component: () => import('@/modules/explore/ExploreView.vue'),
    meta: { title: 'Explore', layout: 'studio', requiresAuth: true, permission: 'dashboard.read', fullBleed: true },
  },

  // Reports
  {
    path: '/reports',
    name: 'reports',
    component: () => import('@/modules/reports/ReportListView.vue'),
    meta: {
      title: 'Reports',
      layout: 'app',
      requiresAuth: true,
      permission: 'report.read',
      entitlement: 'report_studio',
    },
  },
  {
    path: '/reports/new',
    name: 'report-new',
    component: () => import('@/modules/reports/ReportBuilderView.vue'),
    meta: {
      title: 'New Report',
      layout: 'studio',
      requiresAuth: true,
      permission: 'report.create',
      entitlement: 'report_studio',
      fullBleed: true,
    },
  },
  {
    path: '/reports/deliveries',
    name: 'deliveries',
    component: () => import('@/modules/reports/DeliveriesView.vue'),
    meta: {
      title: 'Scheduled Deliveries',
      layout: 'app',
      requiresAuth: true,
      permission: 'report.read',
      entitlement: 'report_studio',
    },
  },
  {
    path: '/reports/:id',
    name: 'report-builder',
    component: () => import('@/modules/reports/ReportBuilderView.vue'),
    meta: {
      title: 'Report',
      layout: 'studio',
      requiresAuth: true,
      permission: 'report.read',
      entitlement: 'report_studio',
      fullBleed: true,
    },
  },

  // AI
  {
    path: '/ai/assistant',
    name: 'ai-assistant',
    component: () => import('@/modules/ai/AssistantView.vue'),
    meta: {
      title: 'AI Assistant',
      layout: 'app',
      requiresAuth: true,
      permission: 'ai.use',
      entitlement: 'ai_studio',
      featureFlag: 'ai_studio',
      developmentMockOnly: true,
      fullBleed: true,
    },
  },
  {
    path: '/ai/studio',
    name: 'ai-studio',
    component: () => import('@/modules/ai/AiStudioView.vue'),
    meta: {
      title: 'AI Studio',
      layout: 'app',
      requiresAuth: true,
      permission: 'ai.configure',
      entitlement: 'ai_studio',
      featureFlag: 'ai_studio',
      developmentMockOnly: true,
    },
  },
  {
    path: '/ai/knowledge',
    name: 'ai-knowledge',
    component: () => import('@/modules/ai/KnowledgeView.vue'),
    meta: {
      title: 'Knowledge Bases',
      layout: 'app',
      requiresAuth: true,
      permission: 'ai.configure',
      entitlement: 'ai_studio',
      featureFlag: 'ai_studio',
      developmentMockOnly: true,
    },
  },
  {
    path: '/ai/agents',
    name: 'ai-agents',
    component: () => import('@/modules/ai/AgentsView.vue'),
    meta: {
      title: 'AI Agents',
      layout: 'app',
      requiresAuth: true,
      permission: 'ai.configure',
      entitlement: 'ai_studio',
      featureFlag: 'ai_studio',
      developmentMockOnly: true,
    },
  },
  {
    path: '/ai/agent-runs',
    name: 'agent-runs',
    component: () => import('@/modules/ai/AgentRunsView.vue'),
    meta: {
      title: 'Agent Runs',
      layout: 'app',
      requiresAuth: true,
      permission: 'ai.configure',
      entitlement: 'ai_studio',
      featureFlag: 'ai_studio',
      developmentMockOnly: true,
    },
  },

  // Automation
  {
    path: '/automation',
    name: 'automation',
    component: () => import('@/modules/automation/AutomationListView.vue'),
    meta: {
      title: 'Automations',
      layout: 'app',
      requiresAuth: true,
      permission: 'automation.read',
      entitlement: 'automation',
    },
  },
  {
    path: '/automation/new',
    name: 'automation-new',
    component: () => import('@/modules/automation/AutomationBuilderView.vue'),
    meta: {
      title: 'New Automation',
      layout: 'studio',
      requiresAuth: true,
      permission: 'automation.write',
      entitlement: 'automation',
      fullBleed: true,
    },
  },
  {
    path: '/automation/runs',
    name: 'automation-runs',
    component: () => import('@/modules/automation/AutomationRunsView.vue'),
    meta: {
      title: 'Automation Runs',
      layout: 'app',
      requiresAuth: true,
      permission: 'automation.read',
      entitlement: 'automation',
    },
  },
  {
    path: '/automation/approvals',
    name: 'approvals',
    component: () => import('@/modules/automation/ApprovalsView.vue'),
    meta: {
      title: 'Approvals',
      layout: 'app',
      requiresAuth: true,
      permission: 'automation.read',
      entitlement: 'automation',
    },
  },
  {
    path: '/automation/:id',
    name: 'automation-builder',
    component: () => import('@/modules/automation/AutomationBuilderView.vue'),
    meta: {
      title: 'Automation',
      layout: 'studio',
      requiresAuth: true,
      permission: 'automation.read',
      entitlement: 'automation',
      fullBleed: true,
    },
  },

  // Operations
  {
    path: '/notifications',
    name: 'notifications',
    component: () => import('@/modules/operations/NotificationsView.vue'),
    meta: { title: 'Notifications', layout: 'app', requiresAuth: true },
  },
  {
    path: '/operations/activity',
    name: 'op-activity',
    component: () => import('@/modules/operations/ActivityCenterView.vue'),
    meta: { title: 'Activity Center', layout: 'app', requiresAuth: true },
  },
  {
    path: '/audit',
    name: 'audit',
    component: () => import('@/modules/operations/AuditCenterView.vue'),
    meta: { title: 'Audit Center', layout: 'app', requiresAuth: true, permission: 'audit.read' },
  },
  {
    path: '/usage',
    name: 'usage',
    component: () => import('@/modules/operations/UsageView.vue'),
    meta: { title: 'Usage', layout: 'app', requiresAuth: true, permission: 'governance.read' },
  },

  // Platform
  {
    path: '/marketplace',
    name: 'marketplace',
    component: () => import('@/modules/marketplace/MarketplaceView.vue'),
    meta: {
      title: 'Marketplace',
      layout: 'app',
      requiresAuth: true,
      permission: 'workspace.read',
      entitlement: 'marketplace',
    },
  },
  {
    path: '/marketplace/:id',
    name: 'marketplace-detail',
    component: () => import('@/modules/marketplace/ExtensionDetailView.vue'),
    meta: {
      title: 'Extension',
      layout: 'app',
      requiresAuth: true,
      permission: 'workspace.read',
      entitlement: 'marketplace',
    },
  },
  {
    path: '/developer',
    name: 'developer',
    component: () => import('@/modules/developer/DeveloperPortalView.vue'),
    meta: {
      title: 'Developer Portal',
      layout: 'app',
      requiresAuth: true,
      permission: 'developer.read',
      entitlement: 'developer_api',
    },
  },

  // Administration
  {
    path: '/admin/platform',
    name: 'admin-platform',
    component: () => import('@/modules/admin/PlatformAdminView.vue'),
    meta: { title: 'Platform Administration', layout: 'app', requiresAuth: true, permission: 'platform.admin' },
  },
  {
    path: '/admin/organization',
    name: 'admin-org',
    component: () => import('@/modules/admin/OrgAdminView.vue'),
    meta: { title: 'Organization Administration', layout: 'app', requiresAuth: true, permission: 'governance.read' },
  },
  {
    path: '/admin/workspace',
    name: 'admin-workspace',
    component: () => import('@/modules/admin/WorkspaceAdminView.vue'),
    meta: { title: 'Workspace Administration', layout: 'app', requiresAuth: true, permission: 'workspace.update' },
  },
  {
    path: '/admin/members',
    name: 'admin-members',
    component: () => import('@/modules/admin/MembersView.vue'),
    meta: { title: 'Members & Roles', layout: 'app', requiresAuth: true, permission: 'governance.read' },
  },
  {
    path: '/admin/roles',
    name: 'admin-roles',
    component: () => import('@/modules/access/RolesView.vue'),
    meta: { title: 'Roles', layout: 'app', requiresAuth: true, permission: 'role.read' },
  },
  {
    path: '/admin/groups',
    name: 'admin-groups',
    component: () => import('@/modules/access/GroupsView.vue'),
    meta: { title: 'Groups & Teams', layout: 'app', requiresAuth: true, permission: 'group.read' },
  },
  {
    path: '/admin/access',
    name: 'admin-access',
    component: () => import('@/modules/access/AccessControlView.vue'),
    meta: {
      title: 'Access Control',
      layout: 'app',
      requiresAuth: true,
      permission: 'resource.permissions.read',
    },
  },
  {
    path: '/admin/feature-flags',
    name: 'admin-flags',
    component: () => import('@/modules/admin/FeatureFlagsView.vue'),
    meta: { title: 'Feature Flags', layout: 'app', requiresAuth: true, permission: 'governance.read' },
  },
  {
    path: '/admin/governance',
    name: 'admin-governance',
    component: () => import('@/modules/admin/GovernanceView.vue'),
    meta: { title: 'Governance', layout: 'app', requiresAuth: true, permission: 'governance.read' },
  },
  {
    path: '/billing',
    name: 'billing',
    component: () => import('@/modules/billing/BillingView.vue'),
    meta: {
      title: 'Billing',
      layout: 'app',
      requiresAuth: true,
      permission: 'billing.read',
      entitlement: 'billing',
    },
  },

  // Help & Documentation
  {
    path: '/help',
    name: 'help',
    component: () => import('@/modules/help/HelpHomeView.vue'),
    meta: { title: 'Help & Docs', requiresAuth: true },
  },
  {
    path: '/help/:slug',
    name: 'help-article',
    component: () => import('@/modules/help/HelpArticleView.vue'),
    meta: { title: 'Help & Docs', requiresAuth: true },
  },

  // Settings — legacy deep links redirect to the correct home so bookmarks
  // never break. Organization/workspace settings now live in Admin; the personal
  // Settings center owns only account-level sections.
  { path: '/settings/personal', redirect: { name: 'settings', params: { section: 'profile' } } },
  { path: '/settings/workspace', redirect: { name: 'admin-workspace' } },
  { path: '/settings/organization', redirect: { name: 'admin-org' } },
  {
    path: '/settings/:section?',
    name: 'settings',
    component: () => import('@/modules/settings/SettingsView.vue'),
    meta: { title: 'Settings', layout: 'settings', requiresAuth: true },
  },

  // Errors
  {
    path: '/forbidden',
    name: 'forbidden',
    component: () => import('@/modules/errors/ForbiddenView.vue'),
    meta: { title: 'Forbidden', layout: 'error' },
  },
  {
    path: '/upgrade',
    name: 'upgrade',
    component: () => import('@/modules/errors/UpgradeView.vue'),
    meta: { title: 'Upgrade Required', layout: 'error' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/modules/errors/NotFoundView.vue'),
    meta: { title: 'Not Found', layout: 'error' },
  },
]

for (const route of routes) {
  if (route.meta?.requiresAuth && route.name !== 'home') {
    route.meta.requiresOrganization ??= true
    route.meta.requiresWorkspace ??= true
  }
}

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
})

router.beforeEach(async (to) => {
  const platform = usePlatformStore()
  const authorization = useAuthorizationStore()
  const auth = useAuthStore()

  if (!auth.initialized) await auth.bootstrap()

  // Guest-only routes (login): send authenticated users home.
  if (to.meta.publicOnly) {
    return auth.isAuthenticated ? { name: 'home' } : true
  }

  // Authentication gate: unauthenticated users go to login, preserving intent.
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    auth.setIntended(to.fullPath)
    return { name: 'login' }
  }

  // Forced password change: a flagged, authenticated user is confined to the
  // change-password screen. The backend independently blocks every business
  // route (PASSWORD_CHANGE_REQUIRED), so this runs before any tenancy or
  // authorization bootstrap to avoid a guaranteed 403. Direct navigation to any
  // other route (including a deep link) is redirected here.
  if (auth.isAuthenticated && auth.mustChangePassword && to.name !== 'force-password-change') {
    return { name: 'force-password-change' }
  }
  if (auth.isAuthenticated && !auth.mustChangePassword && to.name === 'force-password-change') {
    return { name: 'home' }
  }

  // Platform super-admin gate: non-disclosing (mirror the backend 404) and
  // independent of any tenant context.
  if (to.meta.requiresPlatformAdmin && !platform.isPlatformAdmin) {
    return { name: 'not-found' }
  }

  if (to.meta.requiresAuth && auth.isAuthenticated && !platform.initialized) {
    await platform.bootstrapTenancy()
  }
  if (to.meta.requiresOrganization && !platform.organization) {
    return { name: 'home', query: { tenant: 'organization-required' } }
  }
  if (to.meta.requiresWorkspace && !platform.workspace) {
    return { name: 'home', query: { tenant: 'workspace-required' } }
  }

  if (to.meta.requiresAuth && platform.workspace && !authorization.initialized) {
    try {
      await authorization.bootstrap()
    } catch {
      return { name: 'forbidden', query: { from: to.fullPath, reason: 'authorization-unavailable' } }
    }
  }
  if (to.meta.permission && !authorization.can(to.meta.permission)) {
    return { name: 'forbidden', query: { from: to.fullPath } }
  }
  if (to.name === 'settings' && to.params.section === 'developer' && !platform.entitled('developer_api')) {
    return { name: 'upgrade', query: { feature: 'developer_api', from: to.fullPath } }
  }
  if (to.meta.entitlement && !platform.entitled(to.meta.entitlement)) {
    return { name: 'upgrade', query: { feature: to.meta.entitlement, from: to.fullPath } }
  }
  if (to.meta.developmentMockOnly && config.apiMode !== 'mock') {
    return { name: 'not-found' }
  }
  if (to.meta.featureFlag && !platform.flagEnabled(to.meta.featureFlag)) {
    return { name: 'not-found' }
  }
  return true
})

router.afterEach((to) => {
  const base = 'VIP — Veltrix Intelligence Platform'
  document.title = to.meta.title ? `${to.meta.title} · ${base}` : base
  document.documentElement.dataset.vipRoute = to.fullPath
  window.dispatchEvent(new CustomEvent('vip:route-settled', { detail: { path: to.fullPath } }))
})
