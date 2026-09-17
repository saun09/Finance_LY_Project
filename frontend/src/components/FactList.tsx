import React from 'react';
import { StyleSheet, View } from 'react-native';
import type { FactOut } from '../api/types';
import { SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';
import { Text } from './Text';

/**
 * The readable half of a Module 9 trace.
 *
 * This replaced a raw key/value tree that rendered stored values verbatim
 * — `horizon: gt_15y`, `emi_to_income_ratio: 0.3` — on the argument that
 * reformatting them would be a reinterpretation the backend never
 * sanctioned. That was faithful and unreadable at once, and transparency a
 * person cannot read is not transparency.
 *
 * The server sends both halves: `value` is the sentence a person would say,
 * and `raw` is what was actually stored. Only `value` is rendered here.
 *
 * An earlier version printed "recorded as 40" under every row, and the screen
 * also carried a "Show the stored record" panel dumping the raw payload. Both
 * were removed: they restated things the reader could already see, and a
 * screen a person reads is not where an audit dump belongs.
 *
 * Auditability did not move anywhere it can't be reached. `raw` is still on
 * the payload, the full stored record is still on the trace response, and the
 * event log itself (GET /users/{id}/events) remains the real audit surface.
 * The backend readability tests assert `value` against `raw`, so the
 * translation is checked in CI rather than by asking every user to check it.
 */
export function FactList({ facts }: { facts?: FactOut[] | null }) {
  const { colors } = useAppTheme();

  // Defaulted rather than assumed. `facts` is a newer field on the trace
  // payload, so a client running against an older backend -- or a cached
  // response from one -- receives a section without it. That is a reason to
  // render nothing, never to take down the whole screen with it.
  const rows = facts ?? [];
  if (rows.length === 0) return null;

  return (
    <View style={styles.list}>
      {rows.map((fact, i) => (
        <View
          key={`${fact.label}-${i}`}
          style={[
            styles.row,
            i > 0 && { borderTopWidth: StyleSheet.hairlineWidth * 1.5, borderTopColor: colors.border },
          ]}
        >
          <Text variant="caption" tone="muted">
            {fact.label}
          </Text>
          <Text variant="bodyMedium">{fact.value}</Text>
          {fact.note ? (
            <Text variant="caption" tone="faint" style={styles.note}>
              {fact.note}
            </Text>
          ) : null}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  list: { marginTop: SPACE.sm },
  row: { gap: 2, paddingVertical: SPACE.sm },
  note: { lineHeight: 18 },
});
