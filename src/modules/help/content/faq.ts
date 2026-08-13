import type { FaqItem } from './types'

/** Concise FAQs grounded in real VIP behavior. Answers avoid backend internals. */
export const HELP_FAQ: FaqItem[] = [
  {
    id: 'org-vs-workspace',
    question: 'What is the difference between an Organization and a Workspace?',
    answer:
      'An organization is your company tenant. A workspace is an isolated area inside the organization where a team keeps its own connections, datasets, pipelines, and dashboards. You always work inside one active workspace.',
    keywords: ['organization', 'workspace', 'difference', 'tenant'],
  },
  {
    id: 'create-workspace',
    question: 'How do I create a new Workspace?',
    answer:
      'Open Administration → Workspaces and select New workspace, then provide a name and URL slug. This requires workspace administration permission; if you do not have it, ask an organization administrator.',
    keywords: ['create', 'workspace', 'new'],
  },
  {
    id: 'invite-user',
    question: 'How do I invite another user?',
    answer:
      'Administrators can open Administration → Members, add or invite a person, choose their role, and assign the workspaces they can access.',
    keywords: ['invite', 'user', 'member', 'add'],
  },
  {
    id: 'data-sources',
    question: 'What data sources can I connect to?',
    answer:
      'VIP connects to supported databases and to file uploads. Create a connection from the Connections module and run its test to confirm access before using it.',
    keywords: ['connect', 'data source', 'database', 'sources'],
  },
  {
    id: 'upload-files',
    question: 'Can I upload CSV or Excel files?',
    answer:
      'Yes. From Datasets, choose Import CSV or Excel, pick a supported file, review the detected columns, and create the dataset.',
    keywords: ['csv', 'excel', 'upload', 'import', 'file'],
  },
  {
    id: 'connection-failed',
    question: 'Why did my connection test fail?',
    answer:
      'A test can fail if the host, port, or database is wrong, the credentials are rejected, or the source is not reachable. Re-check the details and run the test again. See the Connection troubleshooting articles for more.',
    keywords: ['connection', 'test', 'failed'],
  },
  {
    id: 'pipeline-failed',
    question: 'Why did my pipeline fail?',
    answer:
      'Common causes are a step missing required configuration, steps connected in an invalid order, or a source that became unavailable during the run. Open the failed run to read its status, then fix the reported step and run again.',
    keywords: ['pipeline', 'failed', 'run', 'error'],
  },
  {
    id: 'dashboard-no-data',
    question: 'Why is my dashboard showing no data?',
    answer:
      'Usually the bound dataset is empty or a filter is excluding all rows. Confirm the dataset has records and relax the widget filters.',
    keywords: ['dashboard', 'no data', 'empty'],
  },
  {
    id: 'how-do-i-publish-a-dashboard',
    question: 'How do I publish a dashboard?',
    answer:
      'Open the dashboard, select Publish, and confirm the version. Published dashboards appear under Published Dashboards, where viewers see the published version rather than your in-progress edits.',
    keywords: ['publish', 'dashboard', 'share'],
  },
  {
    id: 'how-do-i-export-a-dashboard',
    question: 'How do I export a dashboard?',
    answer:
      'Open the dashboard, select Export, and choose PDF or PNG. Exports run in the background; download the file when it is ready.',
    keywords: ['export', 'dashboard', 'pdf', 'png'],
  },
  {
    id: 'what-permissions-do-i-need',
    question: 'What permissions do I need to perform an action?',
    answer:
      'Access is controlled by your role and any resource permissions in your workspace. If an action is unavailable, you likely lack the required permission — ask a workspace or organization administrator.',
    keywords: ['permissions', 'role', 'access', 'rbac'],
  },
  {
    id: 'can-multiple-users-work-in-the-same-workspace',
    question: 'Can multiple users work in the same Workspace?',
    answer:
      'Yes. A workspace is shared by its members. What each member can see and do depends on their role and permissions.',
    keywords: ['multiple', 'users', 'collaborate', 'workspace'],
  },
  {
    id: 'where-can-i-see-failed-jobs',
    question: 'Where can I see failed jobs or pipeline runs?',
    answer:
      'Pipeline runs and their status are available from the pipeline’s run history, and platform activity is recorded in Operations → Activity and the Audit Center.',
    keywords: ['failed', 'jobs', 'runs', 'history', 'activity'],
  },
  {
    id: 'how-do-i-report-a-bug',
    question: 'How do I report a bug?',
    answer:
      'Open Help & Docs and use Report a Bug in the “Need more help?” section. It captures useful, non-sensitive context (your current page, workspace, browser, app version, and time) that you can include with your report.',
    keywords: ['report', 'bug', 'support', 'issue'],
  },
]
