/**
 * Server-authoritative file format capabilities (VIP-BUG-007).
 * Prefer this over hard-coded accept= lists in upload UIs.
 */
import { apiClient } from '@/shared/lib/apiClient'

export interface FormatCapability {
  supported: boolean
  extensions: string[]
  mime_types: string[]
  role: 'upload_only' | 'tabular_ingest' | 'unsupported'
  notes: string
}

export interface FileFormatCapabilities {
  schema_version: number
  formats: Record<string, FormatCapability>
  upload_extensions: string[]
  upload_mime_types: string[]
  tabular_ingest_extensions: string[]
  local_file_description: string
}

let cached: FileFormatCapabilities | null = null

export async function loadFileFormatCapabilities(force = false): Promise<FileFormatCapabilities> {
  if (cached && !force) return cached
  cached = await apiClient.get<FileFormatCapabilities>('/files/capabilities')
  return cached
}

/** Accept attribute for tabular dataset upload (CSV + XLSX + browser TSV/TXT). */
export function tabularAcceptAttribute(capabilities?: FileFormatCapabilities | null): string {
  const extensions = new Set<string>(['.csv', '.tsv', '.txt', '.xlsx'])
  for (const ext of capabilities?.tabular_ingest_extensions ?? []) {
    extensions.add(ext.toLowerCase())
  }
  return [...extensions].sort().join(',')
}

export function isLegacyXlsFilename(name: string): boolean {
  return name.toLowerCase().endsWith('.xls') && !name.toLowerCase().endsWith('.xlsx')
}

export function isXlsxFilename(name: string): boolean {
  return name.toLowerCase().endsWith('.xlsx')
}
