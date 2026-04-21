import { IndicatorMetadata } from '../api/securityScanApi';

export const SECURITY_SCAN_INDICATOR_MRU_STORAGE_KEY =
  'optionstrat.securityScan.indicatorDashboard.mru.v1';

export interface IndicatorMruItem {
  indicator_id: string;
  label: string;
  last_used_at: string;
}

function isIndicatorMruItem(value: unknown): value is IndicatorMruItem {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const item = value as Record<string, unknown>;
  return (
    typeof item.indicator_id === 'string' &&
    item.indicator_id.trim().length > 0 &&
    typeof item.label === 'string' &&
    item.label.trim().length > 0 &&
    typeof item.last_used_at === 'string' &&
    item.last_used_at.trim().length > 0
  );
}

export function parseIndicatorMruItems(rawValue: string | null): IndicatorMruItem[] {
  if (!rawValue) {
    return [];
  }

  try {
    const parsed = JSON.parse(rawValue);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(isIndicatorMruItem).slice(0, 5);
  } catch {
    return [];
  }
}

export function readIndicatorMruItems(): IndicatorMruItem[] {
  if (typeof window === 'undefined') {
    return [];
  }

  try {
    return parseIndicatorMruItems(
      window.localStorage.getItem(SECURITY_SCAN_INDICATOR_MRU_STORAGE_KEY)
    );
  } catch {
    return [];
  }
}

export function writeIndicatorMruItems(items: IndicatorMruItem[]): void {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    window.localStorage.setItem(
      SECURITY_SCAN_INDICATOR_MRU_STORAGE_KEY,
      JSON.stringify(items.slice(0, 5))
    );
  } catch {
    return;
  }
}

export function updateIndicatorMruItems(
  currentItems: IndicatorMruItem[],
  indicator: IndicatorMetadata,
  now = new Date()
): IndicatorMruItem[] {
  const nextItem: IndicatorMruItem = {
    indicator_id: indicator.id,
    label: indicator.label,
    last_used_at: now.toISOString(),
  };

  return [
    nextItem,
    ...currentItems.filter((item) => item.indicator_id !== indicator.id),
  ].slice(0, 5);
}

export function filterMruByMetadata(
  items: IndicatorMruItem[],
  indicators: IndicatorMetadata[]
): IndicatorMruItem[] {
  const supportedIds = new Set(indicators.map((indicator) => indicator.id));
  return items.filter((item) => supportedIds.has(item.indicator_id));
}
