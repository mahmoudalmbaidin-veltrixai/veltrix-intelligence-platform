import { describe, it, expect } from 'vitest'
import { validateFormula, FORMULA_FUNCTIONS } from './formulaFunctions'

describe('formula validator', () => {
  it('accepts a valid Excel-like formula', () => {
    const r = validateFormula('IF([revenue] > 0, ROUND([profit] / [revenue], 2), 0)')
    expect(r.valid).toBe(true)
    expect(r.usedFunctions).toEqual(expect.arrayContaining(['IF', 'ROUND']))
    expect(r.usedColumns).toEqual(expect.arrayContaining(['revenue', 'profit']))
  })
  it('flags an empty formula', () => {
    expect(validateFormula('   ').valid).toBe(false)
  })
  it('detects unbalanced parentheses', () => {
    const r = validateFormula('SUM([a], [b]')
    expect(r.valid).toBe(false)
    expect(r.errors.join(' ')).toMatch(/parentheses/i)
  })
  it('detects unknown functions', () => {
    const r = validateFormula('FOObar([a])')
    expect(r.valid).toBe(false)
    expect(r.errors.join(' ')).toMatch(/unknown function/i)
  })
  it('detects unterminated strings', () => {
    expect(validateFormula('CONCAT([a], "x)').valid).toBe(false)
  })
  it('exposes a non-empty function catalog with signatures', () => {
    expect(FORMULA_FUNCTIONS.length).toBeGreaterThan(20)
    expect(FORMULA_FUNCTIONS.every((f) => f.signature && f.example)).toBe(true)
  })
})
