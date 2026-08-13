import type { HelpArticle } from './types'

/**
 * Help articles. Content is deliberately concise and describes only capabilities
 * that genuinely exist in VIP today (Connections, Datasets incl. CSV/Excel
 * import, Pipelines, Dashboards incl. publish + PDF/PNG export, Workspaces,
 * members, data quality, run history). Placeholder/preview surfaces are not
 * documented as generally available.
 */

const gettingStarted: HelpArticle[] = [
  {
    slug: 'welcome-to-vip',
    title: 'Welcome to VIP',
    description: 'A quick orientation to the Veltrix Intelligence Platform.',
    category: 'getting-started',
    keywords: ['welcome', 'intro', 'overview', 'start'],
    body: [
      {
        kind: 'para',
        text: 'Veltrix Intelligence Platform (VIP) helps your team connect to data, prepare it in pipelines, and turn it into interactive dashboards — all within a governed, multi-tenant workspace.',
      },
      {
        kind: 'para',
        text: 'A typical journey moves left to right: connect a data source, register a dataset, build a pipeline to shape the data, create a dashboard, then publish or export the result.',
      },
      { kind: 'subhead', text: 'The core building blocks' },
      {
        kind: 'list',
        items: [
          'Connections — links to your databases and files.',
          'Datasets — governed tables you can query and visualize.',
          'Pipelines — steps that clean, combine, and transform data.',
          'Dashboards — interactive analytics built from datasets.',
        ],
      },
      {
        kind: 'note',
        text: 'What you can see and do depends on your role and the permissions granted in your workspace.',
      },
    ],
    related: ['platform-overview', 'connect-your-first-data-source'],
  },
  {
    slug: 'platform-overview',
    title: 'Platform Overview',
    description: 'How organizations, workspaces, and the main modules fit together.',
    category: 'getting-started',
    keywords: ['overview', 'organization', 'workspace', 'modules', 'navigation'],
    body: [
      {
        kind: 'para',
        text: 'VIP is organized into organizations and workspaces. An organization is your company tenant; a workspace is an isolated area inside it where a team keeps its connections, datasets, pipelines, and dashboards.',
      },
      { kind: 'subhead', text: 'Where things live' },
      {
        kind: 'list',
        items: [
          'Data — Connections, Datasets, Pipelines, Semantic Models, and Data Quality.',
          'Analytics — Dashboard Studio and Published Dashboards.',
          'Operations — Notifications, Activity, and the Audit Center for history.',
          'Administration — members, roles, and workspace settings.',
        ],
      },
      {
        kind: 'para',
        text: 'Use the left sidebar to move between modules. Your account, appearance, and security settings live under Settings.',
      },
    ],
    related: ['create-or-access-a-workspace', 'welcome-to-vip'],
  },
  {
    slug: 'create-or-access-a-workspace',
    title: 'Create or Access a Workspace',
    description: 'Switch between workspaces or create a new one.',
    category: 'getting-started',
    keywords: ['workspace', 'switch', 'create', 'organization'],
    body: [
      {
        kind: 'para',
        text: 'You always work inside one active workspace. Use the organization/workspace switcher in the top bar to change which workspace you are viewing.',
      },
      { kind: 'subhead', text: 'Create a workspace' },
      {
        kind: 'steps',
        items: [
          'Open Administration → Workspaces (requires workspace administration permission).',
          'Select New workspace.',
          'Enter a name and a URL slug (lowercase letters, numbers, and hyphens).',
          'Save. The new workspace becomes available in the switcher.',
        ],
      },
      {
        kind: 'note',
        text: 'If you do not see workspace administration, ask an organization administrator to create the workspace or grant you access.',
      },
    ],
    related: ['invite-team-members', 'platform-overview'],
  },
  {
    slug: 'connect-your-first-data-source',
    title: 'Connect Your First Data Source',
    description: 'Register a connection so VIP can read your data.',
    category: 'getting-started',
    keywords: ['connection', 'data source', 'database', 'connect'],
    body: [
      {
        kind: 'para',
        text: 'A connection tells VIP how to reach your data. Once a connection is active, you can discover tables from it or upload files into it.',
      },
      {
        kind: 'steps',
        items: [
          'Open Connections.',
          'Select New connection and choose a connector type.',
          'Enter the connection details (host, database, and credentials).',
          'Run the connection test to confirm VIP can reach the source.',
          'Save the connection.',
        ],
      },
      {
        kind: 'note',
        text: 'Credentials are stored encrypted and are never shown back to you after saving.',
      },
    ],
    related: ['connect-a-data-source', 'create-your-first-dataset'],
  },
  {
    slug: 'create-your-first-dataset',
    title: 'Create Your First Dataset',
    description: 'Register a dataset from a connection or an uploaded file.',
    category: 'getting-started',
    keywords: ['dataset', 'discover', 'upload', 'table'],
    body: [
      {
        kind: 'para',
        text: 'A dataset is a governed table VIP can query. You can create one by discovering tables from a database connection, or by importing a CSV or Excel file.',
      },
      {
        kind: 'steps',
        items: [
          'Open Datasets.',
          'Choose to discover from a connection, or to import a CSV/Excel file.',
          'Review the detected columns and data types.',
          'Confirm the dataset name and create it.',
        ],
      },
    ],
    related: ['create-a-dataset', 'upload-csv-or-excel', 'build-your-first-pipeline'],
  },
  {
    slug: 'build-your-first-pipeline',
    title: 'Build Your First Pipeline',
    description: 'Shape and combine data with a pipeline.',
    category: 'getting-started',
    keywords: ['pipeline', 'transform', 'clean', 'combine', 'prepare'],
    body: [
      {
        kind: 'para',
        text: 'Pipelines let you clean, combine, and transform datasets into a shape that is ready for analysis. You author a pipeline visually and then run it to produce output.',
      },
      {
        kind: 'steps',
        items: [
          'Open Pipelines and create a new pipeline.',
          'Add a source step that reads from a dataset.',
          'Add transformation steps to filter, join, or reshape the data.',
          'Configure each step and connect them in order.',
          'Save the pipeline, then run it to produce results.',
        ],
      },
      {
        kind: 'note',
        text: 'Every step must be configured before the pipeline can run. Validation highlights any missing configuration.',
      },
    ],
    related: ['build-a-pipeline', 'run-a-pipeline', 'create-your-first-dashboard'],
  },
  {
    slug: 'create-your-first-dashboard',
    title: 'Create Your First Dashboard',
    description: 'Turn a dataset into interactive analytics.',
    category: 'getting-started',
    keywords: ['dashboard', 'visualization', 'chart', 'analytics'],
    body: [
      {
        kind: 'para',
        text: 'Dashboards turn datasets into interactive charts and tables. You build them in Dashboard Studio by adding widgets and binding them to your data.',
      },
      {
        kind: 'steps',
        items: [
          'Open Dashboard Studio and create a new dashboard.',
          'Add a widget (for example a chart, table, KPI, or pivot).',
          'Bind the widget to a dataset and choose the fields to display.',
          'Arrange the widgets and save the dashboard.',
          'Publish the dashboard when you are ready to share it.',
        ],
      },
    ],
    related: ['create-a-dashboard', 'publish-a-dashboard', 'export-dashboard-to-pdf'],
  },
]

const quickGuides: HelpArticle[] = [
  {
    slug: 'connect-a-data-source',
    title: 'Connect a Data Source',
    description: 'Create and test a connection to a database.',
    category: 'quick-guides',
    keywords: ['connection', 'database', 'connect', 'test'],
    body: [
      {
        kind: 'steps',
        items: [
          'Open Connections.',
          'Select New connection.',
          'Choose the connector type that matches your source.',
          'Enter host, database, and credentials.',
          'Run the connection test.',
          'Save the connection once the test passes.',
        ],
      },
    ],
    related: ['connection-test-failed', 'create-a-dataset'],
  },
  {
    slug: 'upload-csv-or-excel',
    title: 'Upload CSV or Excel',
    description: 'Import a CSV or Excel file as a dataset.',
    category: 'quick-guides',
    keywords: ['csv', 'excel', 'upload', 'import', 'file'],
    body: [
      {
        kind: 'steps',
        items: [
          'Open Datasets.',
          'Select Import CSV or Excel.',
          'Choose a supported CSV or Excel file.',
          'Review the detected columns and data types.',
          'Confirm the dataset name.',
          'Create the dataset.',
        ],
      },
      {
        kind: 'note',
        text: 'Very large files may take longer to process. If an upload is rejected, check the file type and that it contains a header row and at least one record.',
      },
    ],
    related: ['upload-failed', 'create-a-dataset'],
  },
  {
    slug: 'create-a-dataset',
    title: 'Create a Dataset',
    description: 'Register a dataset by discovering tables from a connection.',
    category: 'quick-guides',
    keywords: ['dataset', 'discover', 'table', 'schema'],
    body: [
      {
        kind: 'steps',
        items: [
          'Open Datasets.',
          'Choose to discover from an existing connection.',
          'Select the schema and table(s) to register.',
          'Review the detected columns and types.',
          'Confirm and create the dataset.',
        ],
      },
    ],
    related: ['connect-a-data-source', 'build-a-pipeline'],
  },
  {
    slug: 'build-a-pipeline',
    title: 'Build a Pipeline',
    description: 'Author a pipeline that transforms your data.',
    category: 'quick-guides',
    keywords: ['pipeline', 'build', 'transform', 'nodes', 'steps'],
    body: [
      {
        kind: 'steps',
        items: [
          'Open Pipelines and create a new pipeline.',
          'Add a source step bound to a dataset.',
          'Add transformation steps and configure each one.',
          'Connect the steps in the order they should run.',
          'Save the pipeline.',
        ],
      },
      { kind: 'note', text: 'Save resolves the pipeline schema so downstream steps see the correct columns.' },
    ],
    related: ['run-a-pipeline', 'pipeline-validation-failed'],
  },
  {
    slug: 'run-a-pipeline',
    title: 'Run a Pipeline',
    description: 'Execute a pipeline and review its result.',
    category: 'quick-guides',
    keywords: ['pipeline', 'run', 'execute', 'schedule'],
    body: [
      {
        kind: 'steps',
        items: [
          'Open the pipeline you want to run.',
          'Select Run to start an execution.',
          'Wait for the run to complete — status updates as it progresses.',
          'Open the run to review the outcome and any messages.',
        ],
      },
      {
        kind: 'note',
        text: 'Pipelines can also run on a schedule. You can review past runs and their status in the run history.',
      },
    ],
    related: ['pipeline-execution-failed', 'build-a-pipeline'],
  },
  {
    slug: 'create-a-dashboard',
    title: 'Create a Dashboard',
    description: 'Build an interactive dashboard from a dataset.',
    category: 'quick-guides',
    keywords: ['dashboard', 'widget', 'chart', 'create'],
    body: [
      {
        kind: 'steps',
        items: [
          'Open Dashboard Studio and create a new dashboard.',
          'Add a widget and bind it to a dataset.',
          'Choose the dimensions and measures to display.',
          'Arrange widgets on the canvas.',
          'Save the dashboard.',
        ],
      },
    ],
    related: ['publish-a-dashboard', 'dashboard-shows-no-data'],
  },
  {
    slug: 'publish-a-dashboard',
    title: 'Publish a Dashboard',
    description: 'Publish a dashboard so others can view it.',
    category: 'quick-guides',
    keywords: ['dashboard', 'publish', 'share', 'viewer'],
    body: [
      {
        kind: 'steps',
        items: [
          'Open the dashboard you want to publish.',
          'Select Publish.',
          'Confirm the version to publish.',
          'Share the published dashboard with your audience.',
        ],
      },
      {
        kind: 'note',
        text: 'Published dashboards appear under Published Dashboards. Viewers see the published version, not your in-progress edits.',
      },
    ],
    related: ['export-dashboard-to-pdf', 'create-a-dashboard'],
  },
  {
    slug: 'export-dashboard-to-pdf',
    title: 'Export Dashboard to PDF',
    description: 'Export a dashboard as a PDF document.',
    category: 'quick-guides',
    keywords: ['export', 'pdf', 'dashboard', 'download'],
    body: [
      {
        kind: 'steps',
        items: [
          'Open the dashboard you want to export.',
          'Select Export and choose PDF.',
          'The export is queued and generated in the background.',
          'Download the file when the export completes.',
        ],
      },
      { kind: 'note', text: 'Exports run asynchronously; larger dashboards take a little longer to generate.' },
    ],
    related: ['export-dashboard-to-png', 'export-failed'],
  },
  {
    slug: 'export-dashboard-to-png',
    title: 'Export Dashboard to PNG',
    description: 'Export a dashboard as a PNG image.',
    category: 'quick-guides',
    keywords: ['export', 'png', 'image', 'dashboard'],
    body: [
      {
        kind: 'steps',
        items: [
          'Open the dashboard you want to export.',
          'Select Export and choose PNG.',
          'The image is generated in the background.',
          'Download it when the export completes.',
        ],
      },
    ],
    related: ['export-dashboard-to-pdf', 'export-failed'],
  },
  {
    slug: 'invite-team-members',
    title: 'Invite Team Members',
    description: 'Add colleagues to your workspace.',
    category: 'quick-guides',
    keywords: ['invite', 'member', 'user', 'team', 'add'],
    body: [
      {
        kind: 'steps',
        items: [
          'Open Administration → Members (requires member management permission).',
          'Select Invite or Add member.',
          'Enter the person’s details and choose a role.',
          'Assign the workspaces they should access.',
          'Send the invitation.',
        ],
      },
      {
        kind: 'note',
        text: 'The role you assign controls what the new member can see and do. Only administrators can manage members.',
      },
    ],
    related: ['create-or-access-a-workspace', 'create-your-first-dashboard'],
  },
]

const troubleshooting: HelpArticle[] = [
  {
    slug: 'connection-test-failed',
    title: 'Connection test failed',
    description: 'The connection test did not succeed.',
    category: 'troubleshooting',
    keywords: ['connection', 'test', 'failed', 'refused'],
    body: [
      { kind: 'subhead', text: 'Problem' },
      { kind: 'para', text: 'Saving or testing a connection reports that VIP could not reach the source.' },
      { kind: 'subhead', text: 'Possible causes' },
      {
        kind: 'list',
        items: [
          'Incorrect host, port, or database name.',
          'The source is not reachable from the platform network.',
          'Firewall rules block the connection.',
        ],
      },
      { kind: 'subhead', text: 'Resolution' },
      {
        kind: 'steps',
        items: [
          'Re-check the host, port, and database values.',
          'Confirm the source accepts connections from the platform.',
          'Re-run the connection test after correcting the details.',
        ],
      },
    ],
    related: ['authentication-failed', 'connection-timeout'],
  },
  {
    slug: 'authentication-failed',
    title: 'Authentication failed',
    description: 'The source rejected the provided credentials.',
    category: 'troubleshooting',
    keywords: ['authentication', 'credentials', 'password', 'failed'],
    body: [
      { kind: 'subhead', text: 'Problem' },
      { kind: 'para', text: 'The connection reached the source, but the credentials were rejected.' },
      { kind: 'subhead', text: 'Possible causes' },
      {
        kind: 'list',
        items: [
          'The username or password is incorrect.',
          'The account lacks permission to connect to that database.',
          'The password was rotated at the source.',
        ],
      },
      { kind: 'subhead', text: 'Resolution' },
      {
        kind: 'steps',
        items: [
          'Re-enter the credentials and save the connection again.',
          'Confirm the account can access the target database.',
          'Ask your database administrator if the credentials are current.',
        ],
      },
    ],
    related: ['connection-test-failed'],
  },
  {
    slug: 'connection-timeout',
    title: 'Connection timeout',
    description: 'The source did not respond in time.',
    category: 'troubleshooting',
    keywords: ['timeout', 'slow', 'connection', 'unreachable'],
    body: [
      { kind: 'subhead', text: 'Problem' },
      { kind: 'para', text: 'The connection attempt timed out before the source responded.' },
      { kind: 'subhead', text: 'Possible causes' },
      {
        kind: 'list',
        items: [
          'The source is temporarily unavailable.',
          'Network latency or firewall delays.',
          'The host or port is wrong.',
        ],
      },
      { kind: 'subhead', text: 'Resolution' },
      {
        kind: 'steps',
        items: [
          'Confirm the source is running and reachable.',
          'Verify the host and port.',
          'Retry the connection test.',
        ],
      },
    ],
    related: ['connection-test-failed'],
  },
  {
    slug: 'upload-failed',
    title: 'Upload failed',
    description: 'A CSV or Excel upload did not complete.',
    category: 'troubleshooting',
    keywords: ['upload', 'csv', 'excel', 'failed', 'import'],
    body: [
      { kind: 'subhead', text: 'Problem' },
      { kind: 'para', text: 'Importing a CSV or Excel file did not create a dataset.' },
      { kind: 'subhead', text: 'Possible causes' },
      {
        kind: 'list',
        items: [
          'The file type is not supported.',
          'The file is empty or has no header row.',
          'The file exceeds the allowed size.',
        ],
      },
      { kind: 'subhead', text: 'Resolution' },
      {
        kind: 'steps',
        items: [
          'Confirm the file is a supported CSV or Excel format.',
          'Ensure the file has a header row and at least one record.',
          'Try a smaller file if the upload was too large.',
        ],
      },
    ],
    related: ['unsupported-file', 'dataset-contains-no-records'],
  },
  {
    slug: 'unsupported-file',
    title: 'Unsupported file',
    description: 'The file format is not accepted.',
    category: 'troubleshooting',
    keywords: ['unsupported', 'file', 'format', 'type'],
    body: [
      { kind: 'subhead', text: 'Problem' },
      { kind: 'para', text: 'The selected file could not be imported because its format is not supported.' },
      { kind: 'subhead', text: 'Resolution' },
      {
        kind: 'steps',
        items: ['Export your data as CSV or a supported Excel format.', 'Re-import the converted file.'],
      },
    ],
    related: ['upload-failed'],
  },
  {
    slug: 'dataset-contains-no-records',
    title: 'Dataset contains no records',
    description: 'The dataset was created but has no rows.',
    category: 'troubleshooting',
    keywords: ['dataset', 'empty', 'no records', 'rows'],
    body: [
      { kind: 'subhead', text: 'Problem' },
      { kind: 'para', text: 'A dataset registered successfully but returns no rows.' },
      { kind: 'subhead', text: 'Possible causes' },
      { kind: 'list', items: ['The source table or file is empty.', 'A filter removed all rows during import.'] },
      { kind: 'subhead', text: 'Resolution' },
      {
        kind: 'steps',
        items: [
          'Confirm the source contains data.',
          'Re-import or re-discover the dataset from a source that has records.',
        ],
      },
    ],
    related: ['upload-failed'],
  },
  {
    slug: 'pipeline-validation-failed',
    title: 'Pipeline validation failed',
    description: 'The pipeline could not be validated.',
    category: 'troubleshooting',
    keywords: ['pipeline', 'validation', 'failed', 'configuration'],
    body: [
      { kind: 'subhead', text: 'Problem' },
      { kind: 'para', text: 'Saving or running a pipeline reports a validation error.' },
      { kind: 'subhead', text: 'Possible causes' },
      {
        kind: 'list',
        items: [
          'A step is missing required configuration.',
          'Steps are not connected in a valid order.',
          'A referenced dataset or field no longer exists.',
        ],
      },
      { kind: 'subhead', text: 'Resolution' },
      {
        kind: 'steps',
        items: [
          'Open each highlighted step and complete its configuration.',
          'Confirm the steps are connected in order.',
          'Re-save and validate the pipeline.',
        ],
      },
    ],
    related: ['required-node-configuration-missing', 'pipeline-execution-failed'],
  },
  {
    slug: 'pipeline-execution-failed',
    title: 'Pipeline execution failed',
    description: 'A pipeline run ended with an error.',
    category: 'troubleshooting',
    keywords: ['pipeline', 'execution', 'run', 'failed', 'error'],
    body: [
      { kind: 'subhead', text: 'Problem' },
      { kind: 'para', text: 'A pipeline started but did not finish successfully.' },
      { kind: 'subhead', text: 'Possible causes' },
      {
        kind: 'list',
        items: [
          'The source became unavailable during the run.',
          'A transformation received unexpected data.',
          'A downstream connection failed.',
        ],
      },
      { kind: 'subhead', text: 'Resolution' },
      {
        kind: 'steps',
        items: [
          'Open the failed run to read its status message.',
          'Confirm the source and any target connections are available.',
          'Fix the reported step and run the pipeline again.',
        ],
      },
    ],
    related: ['pipeline-validation-failed', 'required-node-configuration-missing'],
  },
  {
    slug: 'required-node-configuration-missing',
    title: 'Required node configuration missing',
    description: 'A pipeline step is not fully configured.',
    category: 'troubleshooting',
    keywords: ['pipeline', 'node', 'step', 'configuration', 'missing'],
    body: [
      { kind: 'subhead', text: 'Problem' },
      { kind: 'para', text: 'A pipeline step is flagged as incomplete and blocks saving or running.' },
      { kind: 'subhead', text: 'Resolution' },
      {
        kind: 'steps',
        items: [
          'Open the highlighted step.',
          'Complete every required field.',
          'Save the pipeline and confirm the warning clears.',
        ],
      },
    ],
    related: ['pipeline-validation-failed'],
  },
  {
    slug: 'dashboard-shows-no-data',
    title: 'Dashboard shows no data',
    description: 'A dashboard widget renders empty.',
    category: 'troubleshooting',
    keywords: ['dashboard', 'no data', 'empty', 'widget'],
    body: [
      { kind: 'subhead', text: 'Problem' },
      { kind: 'para', text: 'A dashboard widget shows no results.' },
      { kind: 'subhead', text: 'Possible causes' },
      {
        kind: 'list',
        items: [
          'The bound dataset is empty or has not been refreshed.',
          'A filter excludes all rows.',
          'The selected fields do not return values.',
        ],
      },
      { kind: 'subhead', text: 'Resolution' },
      {
        kind: 'steps',
        items: [
          'Confirm the underlying dataset contains records.',
          'Relax or clear filters on the widget.',
          'Re-check the fields bound to the widget.',
        ],
      },
    ],
    related: ['visualization-failed-to-load', 'create-a-dashboard'],
  },
  {
    slug: 'visualization-failed-to-load',
    title: 'Visualization failed to load',
    description: 'A widget could not render.',
    category: 'troubleshooting',
    keywords: ['visualization', 'chart', 'failed', 'load'],
    body: [
      { kind: 'subhead', text: 'Problem' },
      { kind: 'para', text: 'A chart or table failed to load in the dashboard.' },
      { kind: 'subhead', text: 'Resolution' },
      {
        kind: 'steps',
        items: [
          'Refresh the dashboard.',
          'Confirm the bound dataset is still available.',
          'Re-open the widget configuration and re-save if needed.',
        ],
      },
    ],
    related: ['dashboard-shows-no-data'],
  },
  {
    slug: 'export-failed',
    title: 'Export failed',
    description: 'A PDF or PNG export did not complete.',
    category: 'troubleshooting',
    keywords: ['export', 'failed', 'pdf', 'png'],
    body: [
      { kind: 'subhead', text: 'Problem' },
      { kind: 'para', text: 'A dashboard export did not produce a file.' },
      { kind: 'subhead', text: 'Possible causes' },
      { kind: 'list', items: ['The export was interrupted.', 'The dashboard changed while the export was running.'] },
      { kind: 'subhead', text: 'Resolution' },
      {
        kind: 'steps',
        items: [
          'Wait for any in-progress export to finish.',
          'Re-run the export.',
          'If it keeps failing, try exporting a simpler version of the dashboard.',
        ],
      },
    ],
    related: ['export-dashboard-to-pdf', 'export-dashboard-to-png'],
  },
]

export const HELP_ARTICLES: HelpArticle[] = [...gettingStarted, ...quickGuides, ...troubleshooting]
