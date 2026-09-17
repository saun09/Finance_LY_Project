import React from 'react';
import { StyleSheet, View } from 'react-native';
import type { ValueHint } from '../api/types';
import { SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';
import { formatTraceValue, humanizeKey } from '../utils/traceValues';
import { Text } from './Text';

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

export type ValueHints = Record<string, ValueHint>;

/** Renders a Module 9 `reasoning` payload as a key/value tree.
 *
 * Originally this component reformatted nothing at all, on the reasoning
 * that guessing whether a raw number was paise, a percentage or a count
 * would be a reinterpretation the backend never sanctioned. That instinct
 * was right, but the conclusion was too strong: it left a non-technical
 * reader looking at `total recoverable annual paise 4560000`, which is
 * faithful and useless at the same time.
 *
 * So the unit now comes from the server (`value_hints`, keyed by leaf name
 * and versioned), and this component formats only leaves it was explicitly
 * told the unit of. Where a value is reformatted, the stored value is
 * printed underneath it -- the readable form is an addition, never a
 * replacement, so this remains an audit trace rather than a summary of one.
 */
export function ReasoningTree({
  data,
  hints,
  depth = 0,
}: {
  data: unknown;
  hints?: ValueHints;
  depth?: number;
}) {
  const { colors } = useAppTheme();

  if (isPlainObject(data)) {
    const entries = Object.entries(data);
    if (entries.length === 0) {
      return (
        <Text variant="caption" tone="faint">
          (empty)
        </Text>
      );
    }
    return (
      <View style={depth > 0 ? [styles.nested, { borderLeftColor: colors.border }] : undefined}>
        {entries.map(([key, value]) => {
          const nested = isPlainObject(value) || Array.isArray(value);
          return (
            <View key={key} style={styles.row}>
              <Text variant={nested ? 'bodyMedium' : 'caption'} tone={nested ? 'ink' : 'muted'}>
                {humanizeKey(key)}
              </Text>
              {nested ? (
                <ReasoningTree data={value} hints={hints} depth={depth + 1} />
              ) : (
                <PrimitiveValue value={value} hint={hints?.[key]} />
              )}
            </View>
          );
        })}
      </View>
    );
  }

  if (Array.isArray(data)) {
    if (data.length === 0) {
      return (
        <Text variant="caption" tone="faint">
          (none)
        </Text>
      );
    }
    return (
      <View style={[styles.nested, { borderLeftColor: colors.border }]}>
        {data.map((item, i) =>
          isPlainObject(item) || Array.isArray(item) ? (
            <View key={i} style={styles.row}>
              <Text variant="caption" tone="faint">
                #{i + 1}
              </Text>
              <ReasoningTree data={item} hints={hints} depth={depth + 1} />
            </View>
          ) : (
            <View key={i} style={styles.row}>
              <PrimitiveValue value={item} />
            </View>
          ),
        )}
      </View>
    );
  }

  return <PrimitiveValue value={data} />;
}

function PrimitiveValue({ value, hint }: { value: unknown; hint?: ValueHint }) {
  if (value === null || value === undefined) {
    return (
      <Text variant="figure" tone="faint">
        —
      </Text>
    );
  }
  if (typeof value === 'boolean') {
    return <Text variant="figure">{value ? 'Yes' : 'No'}</Text>;
  }

  const formatted = formatTraceValue(value, hint);
  return (
    <View>
      <Text variant="figure">{formatted.display}</Text>
      {formatted.showRaw ? (
        <Text variant="caption" tone="faint">
          stored as {formatted.raw}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { gap: 2, marginTop: SPACE.xs },
  nested: { marginLeft: SPACE.sm, paddingLeft: SPACE.sm, borderLeftWidth: StyleSheet.hairlineWidth * 1.5 },
});
