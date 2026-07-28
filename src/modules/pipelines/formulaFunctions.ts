import { apiClient } from '@/shared/lib/apiClient'

export interface FormulaFn {
  name: string
  category: 'Math' | 'Text' | 'Logical' | 'Conversion' | 'Date'
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
    name: "abs",
    category: "Math",
    signature: "abs(number)",
    description: "Returns the absolute numeric value.",
    example: "abs([variance])",
  },
  {
    name: "ceil",
    category: "Math",
    signature: "ceil(number)",
    description: "Rounds a number up to the nearest integer.",
    example: "ceil([quantity])",
  },
  {
    name: "floor",
    category: "Math",
    signature: "floor(number)",
    description: "Rounds a number down to the nearest integer.",
    example: "floor([quantity])",
  },
  {
    name: "round",
    category: "Math",
    signature: "round(number, digits)",
    description: "Rounds a number to the requested decimal places.",
    example: "round([gross_profit] / [net_revenue] * 100, 2)",
  },
  {
    name: "coalesce",
    category: "Logical",
    signature: "coalesce(value, ...)",
    description: "Returns the first non-null value.",
    example: "coalesce([customer_name], \"Unknown\")",
  },
  {
    name: "concat",
    category: "Text",
    signature: "concat(value, ...)",
    description: "Concatenates values as text.",
    example: "concat([country], \" - \", [city])",
  },
  {
    name: "lower",
    category: "Text",
    signature: "lower(text)",
    description: "Converts text to lowercase.",
    example: "lower([email])",
  },
  {
    name: "upper",
    category: "Text",
    signature: "upper(text)",
    description: "Converts text to uppercase.",
    example: "upper([region])",
  },
  {
    name: "mod",
    category: "Math",
    signature: "mod(number, divisor)",
    description: "Remainder after division (null if the divisor is 0).",
    example: "mod([row_id], 10)",
  },
  {
    name: "pow",
    category: "Math",
    signature: "pow(base, exponent)",
    description: "Raises a base to the power of an exponent.",
    example: "pow([side], 2)",
  },
  {
    name: "sqrt",
    category: "Math",
    signature: "sqrt(number)",
    description: "Square root (null for negative numbers).",
    example: "sqrt([area])",
  },
  {
    name: "exp",
    category: "Math",
    signature: "exp(number)",
    description: "Returns e raised to the given power.",
    example: "exp([rate])",
  },
  {
    name: "ln",
    category: "Math",
    signature: "ln(number)",
    description: "Natural logarithm (null for values <= 0).",
    example: "ln([value])",
  },
  {
    name: "log",
    category: "Math",
    signature: "log(number, base)",
    description: "Logarithm of a number in the given base (default 10).",
    example: "log([value], 2)",
  },
  {
    name: "log10",
    category: "Math",
    signature: "log10(number)",
    description: "Base-10 logarithm (null for values <= 0).",
    example: "log10([value])",
  },
  {
    name: "min",
    category: "Math",
    signature: "min(number, ...)",
    description: "Smallest of the given numbers.",
    example: "min([a], [b], 0)",
  },
  {
    name: "max",
    category: "Math",
    signature: "max(number, ...)",
    description: "Largest of the given numbers.",
    example: "max([a], [b], 0)",
  },
  {
    name: "sign",
    category: "Math",
    signature: "sign(number)",
    description: "Returns -1, 0, or 1 for the sign of a number.",
    example: "sign([variance])",
  },
  {
    name: "trunc",
    category: "Math",
    signature: "trunc(number)",
    description: "Truncates toward zero (drops the fractional part).",
    example: "trunc([amount])",
  },
  {
    name: "clamp",
    category: "Math",
    signature: "clamp(number, min, max)",
    description: "Constrains a number to the range [min, max].",
    example: "clamp([score], 0, 100)",
  },
  {
    name: "length",
    category: "Text",
    signature: "length(text)",
    description: "Number of characters in the text.",
    example: "length([name])",
  },
  {
    name: "trim",
    category: "Text",
    signature: "trim(text)",
    description: "Removes leading and trailing whitespace.",
    example: "trim([name])",
  },
  {
    name: "ltrim",
    category: "Text",
    signature: "ltrim(text)",
    description: "Removes leading whitespace.",
    example: "ltrim([code])",
  },
  {
    name: "rtrim",
    category: "Text",
    signature: "rtrim(text)",
    description: "Removes trailing whitespace.",
    example: "rtrim([code])",
  },
  {
    name: "left",
    category: "Text",
    signature: "left(text, count)",
    description: "First N characters of the text.",
    example: "left([sku], 3)",
  },
  {
    name: "right",
    category: "Text",
    signature: "right(text, count)",
    description: "Last N characters of the text.",
    example: "right([sku], 4)",
  },
  {
    name: "substring",
    category: "Text",
    signature: "substring(text, start, length)",
    description: "Substring from a 0-based start position (length optional).",
    example: "substring([code], 2, 4)",
  },
  {
    name: "replace",
    category: "Text",
    signature: "replace(text, find, replacement)",
    description: "Replaces every occurrence of a substring.",
    example: "replace([phone], \"-\", \"\")",
  },
  {
    name: "contains",
    category: "Text",
    signature: "contains(text, search)",
    description: "True if the text contains the search value.",
    example: "contains([email], \"@\")",
  },
  {
    name: "startswith",
    category: "Text",
    signature: "startswith(text, prefix)",
    description: "True if the text starts with the prefix.",
    example: "startswith([sku], \"US-\")",
  },
  {
    name: "endswith",
    category: "Text",
    signature: "endswith(text, suffix)",
    description: "True if the text ends with the suffix.",
    example: "endswith([filename], \".csv\")",
  },
  {
    name: "indexof",
    category: "Text",
    signature: "indexof(text, search)",
    description: "0-based position of the search value, or -1 if absent.",
    example: "indexof([email], \"@\")",
  },
  {
    name: "padleft",
    category: "Text",
    signature: "padleft(text, width, pad)",
    description: "Pads text on the left to a fixed width (default space).",
    example: "padleft([id], 6, \"0\")",
  },
  {
    name: "padright",
    category: "Text",
    signature: "padright(text, width, pad)",
    description: "Pads text on the right to a fixed width (default space).",
    example: "padright([code], 6, \" \")",
  },
  {
    name: "title",
    category: "Text",
    signature: "title(text)",
    description: "Converts text to Title Case.",
    example: "title([name])",
  },
  {
    name: "reverse",
    category: "Text",
    signature: "reverse(text)",
    description: "Reverses the characters in the text.",
    example: "reverse([code])",
  },
  {
    name: "if",
    category: "Logical",
    signature: "if(condition, when_true, when_false)",
    description: "Returns one value when the condition is true, another when false.",
    example: "if([score] >= 50, \"pass\", \"fail\")",
  },
  {
    name: "isnull",
    category: "Logical",
    signature: "isnull(value)",
    description: "True if the value is null.",
    example: "isnull([email])",
  },
  {
    name: "isempty",
    category: "Logical",
    signature: "isempty(value)",
    description: "True if the value is null or an empty string.",
    example: "isempty([note])",
  },
  {
    name: "isnumber",
    category: "Logical",
    signature: "isnumber(value)",
    description: "True if the value is numeric.",
    example: "isnumber([amount])",
  },
  {
    name: "istext",
    category: "Logical",
    signature: "istext(value)",
    description: "True if the value is text.",
    example: "istext([code])",
  },
  {
    name: "ifnull",
    category: "Logical",
    signature: "ifnull(value, fallback)",
    description: "Returns the value, or the fallback when it is null.",
    example: "ifnull([discount], 0)",
  },
  {
    name: "tonumber",
    category: "Conversion",
    signature: "tonumber(value)",
    description: "Converts a value to a number (null if not numeric).",
    example: "tonumber([amount_text])",
  },
  {
    name: "tostring",
    category: "Conversion",
    signature: "tostring(value)",
    description: "Converts a value to text.",
    example: "tostring([row_id])",
  },
  {
    name: "toint",
    category: "Conversion",
    signature: "toint(value)",
    description: "Converts a value to an integer, truncating decimals.",
    example: "toint([price])",
  },
  {
    name: "tobool",
    category: "Conversion",
    signature: "tobool(value)",
    description: "Converts a value to true or false.",
    example: "tobool([flag])",
  },
  {
    name: "in",
    category: "Logical",
    signature: "in(value, option, ...)",
    description: "True if the value equals one of the following options.",
    example: "in([status], \"active\", \"trial\")",
  },
  {
    name: "now",
    category: "Date",
    signature: "now()",
    description: "Current UTC date and time.",
    example: "now()",
  },
  {
    name: "today",
    category: "Date",
    signature: "today()",
    description: "Current UTC date (no time component).",
    example: "today()",
  },
  {
    name: "year",
    category: "Date",
    signature: "year(date)",
    description: "Four-digit year of a date.",
    example: "year([created_at])",
  },
  {
    name: "month",
    category: "Date",
    signature: "month(date)",
    description: "Month number (1-12) of a date.",
    example: "month([created_at])",
  },
  {
    name: "day",
    category: "Date",
    signature: "day(date)",
    description: "Day of the month (1-31) of a date.",
    example: "day([created_at])",
  },
  {
    name: "hour",
    category: "Date",
    signature: "hour(date)",
    description: "Hour (0-23) of a timestamp.",
    example: "hour([created_at])",
  },
  {
    name: "minute",
    category: "Date",
    signature: "minute(date)",
    description: "Minute (0-59) of a timestamp.",
    example: "minute([created_at])",
  },
  {
    name: "datediff",
    category: "Date",
    signature: "datediff(start, end, unit)",
    description: "Whole units from start to end (days, hours, minutes, seconds).",
    example: "datediff([opened_at], [closed_at], \"days\")",
  },
  {
    name: "dateadd",
    category: "Date",
    signature: "dateadd(date, amount, unit)",
    description: "Adds an amount of units to a date (days, hours, minutes, seconds, weeks).",
    example: "dateadd([start_date], 7, \"days\")",
  },
  {
    name: "dateformat",
    category: "Date",
    signature: "dateformat(date, pattern)",
    description: "Formats a date to text using a strftime pattern.",
    example: "dateformat([created_at], \"%Y-%m-%d\")",
  },
  {
    name: "dateparse",
    category: "Date",
    signature: "dateparse(text, pattern)",
    description: "Parses text into a date using a strftime pattern.",
    example: "dateparse([raw_date], \"%m/%d/%Y\")",
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
    this.expression()
    if (this.peek().kind !== 'eof') throw new Error('Unexpected formula content')
  }
  private peek(): FormulaToken {
    return this.items[this.index]
  }
  private take(): FormulaToken {
    return this.items[this.index++]
  }
  private keyword(): string | null {
    const token = this.peek()
    return token.kind === 'name' ? token.value.toLowerCase() : null
  }
  private expectKeyword(kw: string): void {
    if (this.keyword() !== kw) throw new Error(`Expected ${kw.toUpperCase()}`)
    this.take()
  }
  private expression(): void {
    this.and()
    while (this.keyword() === 'or') {
      this.take()
      this.and()
    }
  }
  private and(): void {
    this.notExpr()
    while (this.keyword() === 'and') {
      this.take()
      this.notExpr()
    }
  }
  private notExpr(): void {
    if (this.keyword() === 'not') {
      this.take()
      this.notExpr()
      return
    }
    this.comparison()
  }
  private ifKeyword(): void {
    // 'if' already consumed: IF <cond> THEN <expr> [ELSEIF..THEN..] [ELSE <expr>] ENDIF
    this.expression()
    this.expectKeyword('then')
    this.expression()
    for (;;) {
      const kw = this.keyword()
      if (kw === 'elseif') {
        this.take()
        this.expression()
        this.expectKeyword('then')
        this.expression()
      } else if (kw === 'else') {
        this.take()
        this.expression()
        this.expectKeyword('endif')
        break
      } else if (kw === 'endif') {
        this.take()
        break
      } else {
        throw new Error('Expected ELSEIF, ELSE, or ENDIF')
      }
    }
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
      if (name === 'if' && this.peek().value !== '(') {
        this.ifKeyword()
        return
      }
      const allowed = new Set(FORMULA_FUNCTIONS.map((item) => item.name))
      if (!allowed.has(name) || this.peek().value !== '(') throw new Error(`Function '${token.value}' is not allowed`)
      this.functions.add(name)
      this.take()
      this.depth++
      if (this.depth > 20) throw new Error('Formula nesting is too deep')
      let argumentCount = 0
      if (this.peek().value !== ')') {
        for (;;) {
          this.expression()
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
      this.expression()
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
