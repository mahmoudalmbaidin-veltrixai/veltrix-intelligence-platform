/** Client-side file download helpers (real browser downloads for exports). */

export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function downloadJson(filename: string, data: unknown): void {
  downloadBlob(filename, new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
}

export function downloadCsv(filename: string, columns: string[], rows: (string | number | boolean | null)[][]): void {
  const escape = (v: string | number | boolean | null) => {
    const s = v == null ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const csv = [columns.map(escape).join(','), ...rows.map((r) => r.map(escape).join(','))].join('\n')
  downloadBlob(filename, new Blob([csv], { type: 'text/csv;charset=utf-8' }))
}

export function downloadText(filename: string, text: string, mime = 'text/plain'): void {
  downloadBlob(filename, new Blob([text], { type: mime }))
}

/** Slugify a name for use in a filename. */
export function slug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'export'
}
