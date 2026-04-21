import type {
  IndicatorMetadata,
  IndicatorParameterMetadata,
} from '../api/securityScanApi';

export type ParameterInputValue = string | boolean;
export type ParameterInputMap = Record<string, ParameterInputValue>;

export function formatDateInput(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function defaultStartDate(): string {
  const date = new Date();
  date.setFullYear(date.getFullYear() - 1);
  return formatDateInput(date);
}

export function defaultEndDate(): string {
  return formatDateInput(new Date());
}

function formatParameterValue(
  value: unknown,
  parameterType: string
): ParameterInputValue {
  if (parameterType === 'boolean') {
    return Boolean(value);
  }
  if (Array.isArray(value)) {
    return value.join(', ');
  }
  if (value === undefined || value === null) {
    return '';
  }
  return String(value);
}

export function buildParameterInputs(indicator: IndicatorMetadata): ParameterInputMap {
  return indicator.parameters.reduce<ParameterInputMap>((inputs, parameter) => {
    inputs[parameter.key] = formatParameterValue(parameter.default, parameter.type);
    return inputs;
  }, {});
}

function parseRequiredText(
  value: ParameterInputValue,
  parameter: IndicatorParameterMetadata
): string {
  if (typeof value !== 'string') {
    throw new Error(`${parameter.label} must be text`);
  }
  const trimmed = value.trim();
  if (!trimmed && parameter.required) {
    throw new Error(`${parameter.label} is required`);
  }
  return trimmed;
}

function parseIntegerInput(
  value: string,
  parameter: IndicatorParameterMetadata
): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed)) {
    throw new Error(`${parameter.label} must be a whole number`);
  }
  if (
    parameter.min !== null &&
    parameter.min !== undefined &&
    parsed < parameter.min
  ) {
    throw new Error(`${parameter.label} must be at least ${parameter.min}`);
  }
  if (
    parameter.max !== null &&
    parameter.max !== undefined &&
    parsed > parameter.max
  ) {
    throw new Error(`${parameter.label} must be at most ${parameter.max}`);
  }
  return parsed;
}

function parseFloatInput(
  value: string,
  parameter: IndicatorParameterMetadata
): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`${parameter.label} must be a number`);
  }
  if (
    parameter.min !== null &&
    parameter.min !== undefined &&
    parsed < parameter.min
  ) {
    throw new Error(`${parameter.label} must be at least ${parameter.min}`);
  }
  if (
    parameter.max !== null &&
    parameter.max !== undefined &&
    parsed > parameter.max
  ) {
    throw new Error(`${parameter.label} must be at most ${parameter.max}`);
  }
  return parsed;
}

function parseIntegerListInput(
  value: string,
  parameter: IndicatorParameterMetadata
): number[] {
  const items = value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
  if (!items.length) {
    throw new Error(`${parameter.label} must include at least one value`);
  }
  return items.map((item) => parseIntegerInput(item, parameter));
}

export function buildSettingsFromInputs(
  indicator: IndicatorMetadata,
  inputs: ParameterInputMap
): Record<string, unknown> {
  const settings: Record<string, unknown> = {};
  for (const parameter of indicator.parameters) {
    const rawValue = inputs[parameter.key];
    if (parameter.type === 'boolean') {
      settings[parameter.key] = Boolean(rawValue);
      continue;
    }

    const textValue = parseRequiredText(rawValue ?? '', parameter);
    if (!textValue && !parameter.required) {
      continue;
    }
    if (parameter.type === 'integer') {
      settings[parameter.key] = parseIntegerInput(textValue, parameter);
    } else if (parameter.type === 'float') {
      settings[parameter.key] = parseFloatInput(textValue, parameter);
    } else if (parameter.type === 'integer_list') {
      settings[parameter.key] = parseIntegerListInput(textValue, parameter);
    } else {
      settings[parameter.key] = textValue;
    }
  }
  return settings;
}

export function parseBenchmarkTickers(value: string): string[] {
  return value
    .split(',')
    .map((ticker) => ticker.trim().toUpperCase())
    .filter(Boolean);
}
