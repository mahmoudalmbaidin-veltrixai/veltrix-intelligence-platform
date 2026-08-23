SELECT 'datasets' AS k, count(*)::bigint AS n FROM datasets
UNION ALL SELECT 'pipelines', count(*) FROM pipelines
UNION ALL SELECT 'pipeline_schedules', count(*) FROM pipeline_schedules
UNION ALL SELECT 'dashboards', count(*) FROM dashboards
UNION ALL SELECT 'dashboard_widgets', count(*) FROM dashboard_widgets
UNION ALL SELECT 'dataset_fields', count(*) FROM dataset_fields
UNION ALL SELECT 'quality_rules', count(*) FROM dataset_quality_rules
UNION ALL SELECT 'quality_results', count(*) FROM dataset_quality_results
UNION ALL SELECT 'users', count(*) FROM users
UNION ALL SELECT 'organizations', count(*) FROM organizations
UNION ALL SELECT 'workspaces', count(*) FROM workspaces
UNION ALL SELECT 'files', count(*) FROM files
UNION ALL SELECT 'file_uploads', count(*) FROM file_uploads
ORDER BY 1;

SELECT count(*) AS cert_like_datasets FROM datasets
 WHERE display_name ILIKE '%cert%'
    OR display_name ILIKE 'QA %'
    OR display_name ILIKE 'CERTV2%';

SELECT w.name, count(d.id) AS datasets
  FROM workspaces w
  LEFT JOIN datasets d ON d.workspace_id = w.id
 WHERE w.name LIKE 'CERTV2-SCALE%'
 GROUP BY w.name
 ORDER BY w.name;

SELECT count(*) AS orphan_widgets
  FROM dashboard_widgets dw
  LEFT JOIN dashboards d ON d.id = dw.dashboard_id
 WHERE d.id IS NULL;

SELECT count(*) AS orphan_schedules
  FROM pipeline_schedules s
  LEFT JOIN pipelines p ON p.id = s.pipeline_id
 WHERE p.id IS NULL;

SELECT count(*) AS schedules_enabled_on_archived
  FROM pipeline_schedules s
  JOIN pipelines p ON p.id = s.pipeline_id
 WHERE s.enabled AND p.archived_at IS NOT NULL;

SELECT enabled, count(*) AS n, count(next_run_at) AS with_next
  FROM pipeline_schedules
 GROUP BY enabled;

SELECT version_num FROM alembic_version;
