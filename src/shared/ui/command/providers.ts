/**
 * Typed global-search provider contract. Each provider returns ranked results
 * for a query. Mock providers back the searchable resource types today; a live
 * provider can be swapped in without changing the command palette.
 */
export interface SearchResult {
  id: string
  title: string
  subtitle?: string
  icon: string
  to: string
  group: string
}

export interface SearchProvider {
  key: string
  label: string
  search(query: string): SearchResult[]
}

function mockProvider(key: string, label: string, icon: string, base: string, records: [string, string, string][]): SearchProvider {
  return {
    key,
    label,
    search(query: string) {
      const q = query.toLowerCase()
      return records
        .filter(([, name]) => !q || name.toLowerCase().includes(q))
        .slice(0, 5)
        .map(([id, name, sub]) => ({ id: `${key}-${id}`, title: name, subtitle: sub, icon, to: `${base}/${id}`, group: label }))
    },
  }
}

export const SEARCH_PROVIDERS: SearchProvider[] = [
  mockProvider('conn', 'Connections', 'plug', '/connections', [
    ['cn_pg_prod', 'Production PostgreSQL', 'PostgreSQL · healthy'],
    ['cn_s3_lake', 'Data Lake (S3)', 'S3 · healthy'],
    ['cn_sf_crm', 'Salesforce CRM', 'REST · degraded'],
  ]),
  mockProvider('pipe', 'Pipelines', 'workflow', '/pipelines', [
    ['pl_revenue', 'Revenue Nightly ETL', 'published · failed'],
    ['pl_customer', 'Customer 360 Build', 'published · succeeded'],
    ['pl_events', 'Event Stream Rollup', 'draft'],
  ]),
  mockProvider('ds', 'Datasets', 'database', '/datasets', [
    ['ds_orders', 'fct_orders', '2.4M rows · certified'],
    ['ds_customers', 'dim_customers', '182K rows · certified'],
    ['ds_events', 'fct_events', '54M rows'],
  ]),
  mockProvider('dash', 'Dashboards', 'chart', '/dashboards', [
    ['db_exec', 'Executive Overview', 'published'],
    ['db_revops', 'Revenue Operations', 'published'],
    ['db_ops', 'Platform Health', 'draft'],
  ]),
  mockProvider('rep', 'Reports', 'report', '/reports', [
    ['rp_board', 'Q3 Board Report', 'in review'],
    ['rp_monthly', 'Monthly Business Review', 'published'],
  ]),
  mockProvider('auto', 'Automations', 'workflow', '/automation', [
    ['au_alert', 'Pipeline Failure Alert', 'active'],
    ['au_refresh', 'Dataset Refresh Notify', 'active'],
  ]),
]
