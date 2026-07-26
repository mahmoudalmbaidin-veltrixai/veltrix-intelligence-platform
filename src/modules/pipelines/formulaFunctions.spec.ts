import { describe, it, expect } from 'vitest'
import { validateFormula, FORMULA_FUNCTIONS } from './formulaFunctions'

describe('formula validator', () => {
  it('accepts a valid governed formula', () => {
    const r = validateFormula('coalesce(round([profit] / [revenue], 2), 0)')
    expect(r.valid).toBe(true)
    expect(r.usedFunctions).toEqual(expect.arrayContaining(['coalesce', 'round']))
    expect(r.usedColumns).toEqual(expect.arrayContaining(['revenue', 'profit']))
  })
  it('flags an empty formula', () => {
    expect(validateFormula('   ').valid).toBe(false)
  })
  it('detects unbalanced parentheses', () => {
    const r = validateFormula('concat([a], [b]')
    expect(r.valid).toBe(false)
    expect(r.errors.join(' ')).toMatch(/parenthesis/i)
  })
  it('detects unknown functions', () => {
    const r = validateFormula('FOObar([a])')
    expect(r.valid).toBe(false)
    expect(r.errors.join(' ')).toMatch(/not allowed/i)
  })
  it('detects unterminated strings', () => {
    expect(validateFormula('concat([a], "x)').valid).toBe(false)
  })
  it('exposes a non-empty function catalog with signatures', () => {
    expect(FORMULA_FUNCTIONS).toHaveLength(8)
    expect(FORMULA_FUNCTIONS.every((f) => f.signature && f.example)).toBe(true)
  })
})
