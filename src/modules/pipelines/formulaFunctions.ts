/**
 * Excel-like formula function catalog + a lightweight validator used by the
 * Formula node's expression builder. This is the frontend contract; the
 * pipeline engine evaluates the compiled expression server-side at run time.
 */
export interface FormulaFn {
  name: string
  category: 'Math' | 'Text' | 'Logical' | 'Date' | 'Aggregate' | 'Conversion'
  signature: string
  description: string
  example: string
}

export const FORMULA_FUNCTIONS: FormulaFn[] = [
  // Math
  { name: 'SUM', category: 'Aggregate', signature: 'SUM(number, …)', description: 'Adds all arguments.', example: 'SUM([revenue], [tax])' },
  { name: 'AVERAGE', category: 'Aggregate', signature: 'AVERAGE(number, …)', description: 'Arithmetic mean of the arguments.', example: 'AVERAGE([q1], [q2], [q3])' },
  { name: 'MIN', category: 'Aggregate', signature: 'MIN(number, …)', description: 'Smallest value.', example: 'MIN([price])' },
  { name: 'MAX', category: 'Aggregate', signature: 'MAX(number, …)', description: 'Largest value.', example: 'MAX([price])' },
  { name: 'COUNT', category: 'Aggregate', signature: 'COUNT(value, …)', description: 'Counts non-null values.', example: 'COUNT([order_id])' },
  { name: 'ROUND', category: 'Math', signature: 'ROUND(number, digits)', description: 'Rounds a number to a given number of digits.', example: 'ROUND([margin], 2)' },
  { name: 'ABS', category: 'Math', signature: 'ABS(number)', description: 'Absolute value.', example: 'ABS([delta])' },
  { name: 'CEILING', category: 'Math', signature: 'CEILING(number)', description: 'Rounds up to the nearest integer.', example: 'CEILING([units])' },
  { name: 'FLOOR', category: 'Math', signature: 'FLOOR(number)', description: 'Rounds down to the nearest integer.', example: 'FLOOR([units])' },
  { name: 'POWER', category: 'Math', signature: 'POWER(base, exp)', description: 'Raises base to a power.', example: 'POWER([x], 2)' },
  { name: 'MOD', category: 'Math', signature: 'MOD(number, divisor)', description: 'Remainder after division.', example: 'MOD([id], 10)' },
  // Text
  { name: 'CONCAT', category: 'Text', signature: 'CONCAT(text, …)', description: 'Joins text values.', example: 'CONCAT([first], " ", [last])' },
  { name: 'UPPER', category: 'Text', signature: 'UPPER(text)', description: 'Converts text to uppercase.', example: 'UPPER([code])' },
  { name: 'LOWER', category: 'Text', signature: 'LOWER(text)', description: 'Converts text to lowercase.', example: 'LOWER([email])' },
  { name: 'TRIM', category: 'Text', signature: 'TRIM(text)', description: 'Removes leading/trailing spaces.', example: 'TRIM([name])' },
  { name: 'LEFT', category: 'Text', signature: 'LEFT(text, n)', description: 'First n characters.', example: 'LEFT([sku], 3)' },
  { name: 'RIGHT', category: 'Text', signature: 'RIGHT(text, n)', description: 'Last n characters.', example: 'RIGHT([sku], 4)' },
  { name: 'LEN', category: 'Text', signature: 'LEN(text)', description: 'Length of the text.', example: 'LEN([name])' },
  { name: 'SUBSTITUTE', category: 'Text', signature: 'SUBSTITUTE(text, old, new)', description: 'Replaces occurrences of old with new.', example: 'SUBSTITUTE([phone], "-", "")' },
  // Logical
  { name: 'IF', category: 'Logical', signature: 'IF(condition, then, else)', description: 'Returns one value if true, another if false.', example: 'IF([revenue] > 0, "active", "none")' },
  { name: 'AND', category: 'Logical', signature: 'AND(cond, …)', description: 'True when all conditions are true.', example: 'AND([a] > 0, [b] > 0)' },
  { name: 'OR', category: 'Logical', signature: 'OR(cond, …)', description: 'True when any condition is true.', example: 'OR([vip], [priority])' },
  { name: 'NOT', category: 'Logical', signature: 'NOT(cond)', description: 'Inverts a boolean.', example: 'NOT([archived])' },
  { name: 'ISNULL', category: 'Logical', signature: 'ISNULL(value)', description: 'True when the value is null.', example: 'ISNULL([email])' },
  { name: 'COALESCE', category: 'Logical', signature: 'COALESCE(value, …)', description: 'First non-null value.', example: 'COALESCE([nick], [name])' },
  // Date
  { name: 'NOW', category: 'Date', signature: 'NOW()', description: 'Current timestamp.', example: 'NOW()' },
  { name: 'TODAY', category: 'Date', signature: 'TODAY()', description: 'Current date.', example: 'TODAY()' },
  { name: 'DATEDIFF', category: 'Date', signature: 'DATEDIFF(unit, start, end)', description: 'Difference between two dates.', example: 'DATEDIFF("day", [created], TODAY())' },
  { name: 'DATEADD', category: 'Date', signature: 'DATEADD(unit, n, date)', description: 'Adds an interval to a date.', example: 'DATEADD("month", 1, [start])' },
  { name: 'YEAR', category: 'Date', signature: 'YEAR(date)', description: 'Year component.', example: 'YEAR([order_date])' },
  { name: 'MONTH', category: 'Date', signature: 'MONTH(date)', description: 'Month component.', example: 'MONTH([order_date])' },
  // Conversion
  { name: 'TONUMBER', category: 'Conversion', signature: 'TONUMBER(text)', description: 'Parses text to a number.', example: 'TONUMBER([amount_str])' },
  { name: 'TOTEXT', category: 'Conversion', signature: 'TOTEXT(value)', description: 'Converts a value to text.', example: 'TOTEXT([id])' },
  { name: 'TODATE', category: 'Conversion', signature: 'TODATE(text)', description: 'Parses text to a date.', example: 'TODATE([date_str])' },
]

export const FUNCTION_NAMES = new Set(FORMULA_FUNCTIONS.map((f) => f.name))

export interface FormulaValidation {
  valid: boolean
  errors: string[]
  usedFunctions: string[]
  usedColumns: string[]
}

/**
 * Static validation: balanced brackets/quotes and recognised function names.
 * (The backend performs full type-checked compilation.)
 */
export function validateFormula(expr: string): FormulaValidation {
  const errors: string[] = []
  const trimmed = expr.trim()
  if (!trimmed) return { valid: false, errors: ['Formula is empty.'], usedFunctions: [], usedColumns: [] }

  // balanced parentheses
  let depth = 0
  for (const ch of trimmed) {
    if (ch === '(') depth++
    else if (ch === ')') depth--
    if (depth < 0) { errors.push('Unbalanced parentheses — unexpected ")".'); break }
  }
  if (depth > 0) errors.push('Unbalanced parentheses — missing ")".')

  // balanced quotes
  const dq = (trimmed.match(/"/g) ?? []).length
  if (dq % 2 !== 0) errors.push('Unterminated string literal.')

  // balanced column brackets
  const open = (trimmed.match(/\[/g) ?? []).length
  const close = (trimmed.match(/\]/g) ?? []).length
  if (open !== close) errors.push('Unbalanced column brackets [ ].')

  // unknown function names (identifier immediately followed by "(")
  const callMatches = [...trimmed.matchAll(/([A-Za-z_][A-Za-z0-9_]*)\s*\(/g)].map((m) => m[1].toUpperCase())
  const unknown = callMatches.filter((n) => !FUNCTION_NAMES.has(n))
  const usedFunctions = [...new Set(callMatches.filter((n) => FUNCTION_NAMES.has(n)))]
  if (unknown.length) errors.push(`Unknown function${unknown.length > 1 ? 's' : ''}: ${[...new Set(unknown)].join(', ')}.`)

  const usedColumns = [...new Set([...trimmed.matchAll(/\[([^\]]+)\]/g)].map((m) => m[1]))]

  return { valid: errors.length === 0, errors, usedFunctions, usedColumns }
}
