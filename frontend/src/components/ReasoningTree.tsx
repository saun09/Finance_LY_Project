import React from 'react';
import { StyleSheet, View } from 'react-native';
import { SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';
import { Text } from './Text';

function humanizeKey(key: string) {
  return key.replace(/_/g, ' ');
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

/** Renders an arbitrary reasoning payload (Module 9's `reasoning` dict)
 * exactly as the backend returned it -- no reformatting, no currency
 * conversion, no reinterpretation of what a raw number means. This is a
 * debug/audit trace, not a display-boundary API field, so the honest
 * choice is to show it as a readable key/value tree rather than guess at
 * which numbers are paise, percentages, or plain counts. */
export function ReasoningTree({ data, depth = 0 }: { data: unknown; depth?: number }) {
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
                <ReasoningTree data={value} depth={depth + 1} />
              ) : (
                <PrimitiveValue value={value} />
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
              <ReasoningTree data={item} depth={depth + 1} />
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

function PrimitiveValue({ value }: { value: unknown }) {
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
  return <Text variant="figure">{String(value)}</Text>;
}

const styles = StyleSheet.create({
  row: { gap: 2, marginTop: SPACE.xs },
  nested: { marginLeft: SPACE.sm, paddingLeft: SPACE.sm, borderLeftWidth: StyleSheet.hairlineWidth * 1.5 },
});
