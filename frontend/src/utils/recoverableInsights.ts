import type { Ionicons } from '@expo/vector-icons';
import type { RecoverableComponentOut } from '../api/types';

export type IconTone = 'terracotta' | 'warning' | 'petrol';
export type IconName = 'cash-outline' | 'card-outline' | 'repeat-outline';
export type ComponentKind = 'idle_cash' | 'fee_drag' | 'recurring';

/** component_id is "idle_cash", "fee_drag:<item>", or "recurring:<item>"
 * (see backend/app/services/leak_engine.py::build_leak_report) -- an
 * icon per prefix, not per exact id, since the suffix is per-user data. */
export function kindOfComponent(componentId: string): ComponentKind {
  if (componentId === 'idle_cash') return 'idle_cash';
  if (componentId.startsWith('fee_drag:')) return 'fee_drag';
  return 'recurring';
}

export const ICON_FOR_KIND: Record<ComponentKind, { icon: keyof typeof Ionicons.glyphMap; tone: IconTone }> = {
  idle_cash: { icon: 'cash-outline', tone: 'terracotta' },
  fee_drag: { icon: 'card-outline', tone: 'warning' },
  recurring: { icon: 'repeat-outline', tone: 'petrol' },
};

/** Backend labels follow "Recurring charge to review: <category>" /
 * "Recurring fee: <category>" -- the bit after the colon is the actual
 * user-entered category text (free-form, e.g. "dining_out"), lightly
 * reformatted for display only (underscores -> spaces, sentence case:
 * only the first letter capitalized), never altering the underlying
 * data. idle_cash has no colon and is already a short, well-formed
 * label, so it's used as-is. */
export function shortCategoryTitle(label: string): string {
  const idx = label.indexOf(': ');
  const raw = idx < 0 ? label : label.slice(idx + 2).replace(/[_-]+/g, ' ');
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

export interface GroupedInsight {
  key: string;
  icon: keyof typeof Ionicons.glyphMap;
  tone: IconTone;
  kind: ComponentKind;
  title: string;
  amountPaise: number;
  count: number;
  /** Every raw record this row collapses, kept (not just counted/summed)
   * so a detail view can list each one's own exact amount and backend-
   * written explanation on expand, instead of a single generic sentence
   * repeated once per category. */
  items: RecoverableComponentOut[];
}

/** Collapses repeat records of the same recommendation (e.g. several
 * "Recurring charge to review: rent" rows -- which happens whenever the
 * stored data genuinely has more than one matching expense item, most
 * commonly duplicate manual entries) into one row with a combined amount
 * and a real count. This groups for *display* only: it never claims the
 * underlying records are confirmed duplicate payments (they may be
 * entirely distinct real expenses that happen to share a category), and
 * every individual record this collapses is still an exact, unmodified
 * stored row -- nothing is hidden, only summed and counted. Grouped by
 * `label` (backend's own category text), shared by both the Home preview
 * and the Leaks detail screen so the two can never show different counts
 * for the same underlying data. */
export function groupByLabel(components: RecoverableComponentOut[]): GroupedInsight[] {
  const byLabel = new Map<string, GroupedInsight>();
  for (const c of components) {
    const existing = byLabel.get(c.label);
    if (existing) {
      existing.amountPaise += c.annual_amount_paise;
      existing.count += 1;
      existing.items.push(c);
    } else {
      const kind = kindOfComponent(c.component_id);
      const { icon, tone } = ICON_FOR_KIND[kind];
      byLabel.set(c.label, {
        key: c.label,
        icon,
        tone,
        kind,
        title: shortCategoryTitle(c.label),
        amountPaise: c.annual_amount_paise,
        count: 1,
        items: [c],
      });
    }
  }
  return Array.from(byLabel.values()).sort((a, b) => b.amountPaise - a.amountPaise);
}
