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
    expect(FORMULA_FUNCTIONS).toHaveLength(58)
    expect(FORMULA_FUNCTIONS.every((f) => f.signature && f.example)).toBe(true)
  })
  it('accepts the expanded Math / Text / Conversion functions', () => {
    const r = validateFormula('if(isnumber(tonumber([amt])), clamp(round([amt], 2), 0, 100), 0)')
    expect(r.valid).toBe(true)
    expect(r.usedFunctions).toEqual(
      expect.arrayContaining(['if', 'isnumber', 'tonumber', 'clamp', 'round']),
    )
  })
  it('accepts and / or / not logical operators', () => {
    expect(validateFormula('[a] > 0 and [b] == 0 or not [c]').valid).toBe(true)
  })
  it('accepts the IF..THEN..ELSEIF..ELSE..ENDIF keyword form', () => {
    const r = validateFormula('if [a] > 10 then "big" elseif [a] > 3 then "mid" else "small" endif')
    expect(r.valid).toBe(true)
    expect(r.usedColumns).toContain('a')
  })
  it('flags an IF keyword form that is missing ENDIF', () => {
    const r = validateFormula('if [a] > 10 then "big"')
    expect(r.valid).toBe(false)
  })
  it('accepts membership and date functions', () => {
    const r = validateFormula('in([status], "active", "trial") and year([created]) == 2024')
    expect(r.valid).toBe(true)
    expect(r.usedFunctions).toEqual(expect.arrayContaining(['in', 'year']))
  })
})
