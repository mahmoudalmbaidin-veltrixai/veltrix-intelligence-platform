import { apiClient } from '@/shared/lib/apiClient'

export interface FormulaFn {
  name: string
  category: 'Math' | 'Text' | 'Logical'
  signature: string
  description: string
  example: string
}

interface FormulaLanguage {
  version: number
  field_syntax: string
  functions: FormulaFn[]
  operators: string[]
  literals: string[]
}

export interface FormulaValidation {
  valid: boolean
  errors: string[]
  usedFunctions: string[]
  usedColumns: string[]
}

interface ApiFormulaValidation {
  valid: boolean
  errors: string[]
  used_functions: string[]
  used_fields: string[]
}

// Exact built-in fallback. The live catalog replaces this array from the
// authoritative parser endpoint when Formula Editor mounts.
export const FORMULA_FUNCTIONS: FormulaFn[] = [
  {
    name: 'abs',
    category: 'Math',
    signature: 'abs(number)',
    description: 'Returns the absolute numeric value.',
    example: 'abs([variance])',
  },
  {
    name: 'ceil',
    category: 'Math',
    signature: 'ceil(number)',
    description: 'Rounds a number up to the nearest integer.',
    example: 'ceil([quantity])',
  },
  {
    name: 'floor',
    category: 'Math',
    signature: 'floor(number)',
    description: 'Rounds a number down to the nearest integer.',
    example: 'floor([quantity])',
  },
  {
    name: 'round',
    category: 'Math',
    signature: 'round(number, digits)',
    description: 'Rounds a number to the requested decimal places.',
    example: 'round([gross_profit] / [net_revenue] * 100, 2)',
  },
  {
    name: 'coalesce',
    category: 'Logical',
    signature: 'coalesce(value, ...)',
    description: 'Returns the first non-null value.',
    example: 'coalesce([customer_name], "Unknown")',
  },
  {
    name: 'concat',
    category: 'Text',
    signature: 'concat(value, ...)',
    description: 'Concatenates values as text.',
    example: 'concat([country], " - ", [city])',
  },
  {
    name: 'lower',
    category: 'Text',
    signature: 'lower(text)',
    description: 'Converts text to lowercase.',
    example: 'lower([email])',
  },
  {
    name: 'upper',
    category: 'Text',
    signature: 'upper(text)',
    description: 'Converts text to uppercase.',
    example: 'upper([region])',
  },
]

let catalogPromise: Promise<FormulaLanguage> | null = null
export async function loadFormulaLanguage(): Promise<FormulaLanguage> {
  catalogPromise ??= apiClient.get<FormulaLanguage>('/pipelines/formula-language')
  const language = await catalogPromise
  FORMULA_FUNCTIONS.splice(0, FORMULA_FUNCTIONS.length, ...language.functions)
  return language
}

export async function validateFormulaRemote(expression: string, availableFields: string[]): Promise<FormulaValidation> {
  if (!expression.trim()) {
    return {
      valid: false,
      errors: ['Formula length must be between 1 and 4096 characters'],
      usedFunctions: [],
      usedColumns: [],
    }
  }
  const result = await apiClient.post<ApiFormulaValidation>('/pipelines/formula-language/validate', {
    expression,
    available_fields: availableFields,
  })
  return {
    valid: result.valid,
    errors: result.errors,
    usedFunctions: result.used_functions,
    usedColumns: result.used_fields,
  }
}

const TOKEN =
  /\s*(?:(?<number>\d+(?:\.\d+)?)|(?<string>"(?:[^"\\]|\\.)*")|(?<field>\[[A-Za-z_][A-Za-z0-9_]{0,127}\])|(?<op><=|>=|!=|==|[()+\-*/,<>])|(?<name>[A-Za-z_][A-Za-z0-9_]*))/y

type FormulaToken = { kind: string; value: string }

function tokens(source: string): FormulaToken[] {
  if (source.length < 1 || source.length > 4096) throw new Error('Formula length must be between 1 and 4096 characters')
  const result: FormulaToken[] = []
  let position = 0
  while (position < source.length) {
    TOKEN.lastIndex = position
    const match = TOKEN.exec(source)
    if (!match?.groups) throw new Error(`Unsupported token at character ${position + 1}`)
    const entry = Object.entries(match.groups).find(([, value]) => value !== undefined)
    if (!entry) throw new Error(`Unsupported token at character ${position + 1}`)
    result.push({ kind: entry[0], value: entry[1] })
    position = TOKEN.lastIndex
    if (result.length > 512) throw new Error('Formula is too complex')
  }
  result.push({ kind: 'eof', value: '' })
  return result
}

class FormulaParser {
  private index = 0
  private depth = 0
  readonly functions = new Set<string>()
  readonly fields = new Set<string>()

  constructor(private readonly items: FormulaToken[]) {}

  parse(): void {
    this.comparison()
    if (this.peek().kind !== 'eof') throw new Error('Unexpected formula content')
  }
  private peek(): FormulaToken {
    return this.items[this.index]
  }
  private take(): FormulaToken {
    return this.items[this.index++]
  }
  private comparison(): void {
    this.sum()
    while (['==', '!=', '<', '<=', '>', '>='].includes(this.peek().value)) {
      this.take()
      this.sum()
    }
  }
  private sum(): void {
    this.product()
    while (['+', '-'].includes(this.peek().value)) {
      this.take()
      this.product()
    }
  }
  private product(): void {
    this.unary()
    while (['*', '/'].includes(this.peek().value)) {
      this.take()
      this.unary()
    }
  }
  private unary(): void {
    if (['+', '-'].includes(this.peek().value)) this.take()
    this.primary()
  }
  private primary(): void {
    const token = this.take()
    if (['number', 'string'].includes(token.kind)) return
    if (token.kind === 'field') {
      this.fields.add(token.value.slice(1, -1))
      return
    }
    if (token.kind === 'name') {
      const name = token.value.toLowerCase()
      if (['true', 'false', 'null'].includes(name)) return
      const allowed = new Set(FORMULA_FUNCTIONS.map((item) => item.name))
      if (!allowed.has(name) || this.peek().value !== '(') throw new Error(`Function '${token.value}' is not allowed`)
      this.functions.add(name)
      this.take()
      this.depth++
      if (this.depth > 20) throw new Error('Formula nesting is too deep')
      let argumentCount = 0
      if (this.peek().value !== ')') {
        for (;;) {
          this.comparison()
          argumentCount++
          if (argumentCount > 20) throw new Error('Function has too many arguments')
          if (this.peek().value !== ',') break
          this.take()
        }
      }
      if (this.take().value !== ')') throw new Error('Expected closing parenthesis')
      this.depth--
      return
    }
    if (token.value === '(') {
      this.comparison()
      if (this.take().value !== ')') throw new Error('Expected closing parenthesis')
      return
    }
    throw new Error('Expected a literal, field, or approved function')
  }
}

/** Deterministic client parser ported from the backend grammar for immediate feedback. */
export function validateFormula(expression: string): FormulaValidation {
  try {
    const parser = new FormulaParser(tokens(expression))
    parser.parse()
    return {
      valid: true,
      errors: [],
      usedFunctions: [...parser.functions].sort(),
      usedColumns: [...parser.fields].sort(),
    }
  } catch (cause) {
    return {
      valid: false,
      errors: [(cause as Error).message],
      usedFunctions: [],
      usedColumns: [],
    }
  }
}
