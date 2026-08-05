export interface BrowserPersona {
  email: string
  password: string
}

function required(name: string): string {
  const value = process.env[name]?.trim()
  if (!value) throw new Error(`Browser fixture setup is incomplete: ${name} is required.`)
  return value
}

function persona(prefix: string): BrowserPersona {
  return {
    email: required(`${prefix}_EMAIL`),
    password: required(`${prefix}_PASSWORD`),
  }
}

export const browserFixtures = {
  primary: persona('VIP_E2E'),
  tenantA: persona('VIP_E2E_TENANT_A'),
  tenantB: persona('VIP_E2E_TENANT_B'),
  governanceAdmin: persona('VIP_E2E_GOVERNANCE_ADMIN'),
  governanceEditor: persona('VIP_E2E_GOVERNANCE_EDITOR'),
  governanceViewer: persona('VIP_E2E_GOVERNANCE_VIEWER'),
  governanceRestricted: persona('VIP_E2E_GOVERNANCE_RESTRICTED'),
  moduleRestricted: persona('VIP_E2E_MODULE_RESTRICTED'),
  normalUser: persona('VIP_E2E_NORMAL_USER'),
  organizationA: required('VIP_E2E_ORGANIZATION_A_NAME'),
  organizationB: required('VIP_E2E_ORGANIZATION_B_NAME'),
  workspaceAPrimary: required('VIP_E2E_WORKSPACE_A_PRIMARY'),
  workspaceASecondary: required('VIP_E2E_WORKSPACE_A_SECONDARY'),
  workspaceBPrimary: required('VIP_E2E_WORKSPACE_B_PRIMARY'),
  tenantAOrganization: required('VIP_E2E_TENANT_A_ORGANIZATION_NAME'),
  tenantAWorkspace: required('VIP_E2E_TENANT_A_WORKSPACE_NAME'),
  tenantBOrganization: required('VIP_E2E_TENANT_B_ORGANIZATION_NAME'),
  tenantBWorkspace: required('VIP_E2E_TENANT_B_WORKSPACE_NAME'),
  destinationConnection: required('VIP_E2E_DESTINATION_CONNECTION_NAME'),
  certificationDataset: required('VIP_E2E_CERTIFICATION_DATASET_NAME'),
  certificationSemanticModel: required('VIP_E2E_CERTIFICATION_SEMANTIC_MODEL_NAME'),
  governanceRestrictedId: required('VIP_E2E_GOVERNANCE_RESTRICTED_ID'),
}
