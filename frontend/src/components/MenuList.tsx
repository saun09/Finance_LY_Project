import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useAppTheme } from '../theme/ThemeContext';
import { SPACE } from '../theme/tokens';
import { Card } from './Card';
import { IconChip } from './IconChip';
import { Text } from './Text';

export interface MenuItem {
  key: string;
  title: string;
  subtitle: string;
  onPress: () => void;
  disabled?: boolean;
  /** Optional leading icon chip -- every existing caller omits this and
   * renders exactly as before; new callers (e.g. Home's "A few things to
   * check") opt in per-row. */
  icon?: keyof typeof Ionicons.glyphMap;
  iconTone?: 'positive' | 'warning' | 'danger' | 'petrol' | 'terracotta';
}

/** A card of tappable rows with an optional icon chip, title/subtitle,
 * and chevron, each separated by a hairline divider -- the shared shape
 * behind Insights, Transparency, Profile's navigation menus, and Home's
 * condensed recommendation list. */
export function MenuList({ items }: { items: MenuItem[] }) {
  const { colors } = useAppTheme();
  return (
    <Card padded={false}>
      {items.map((item, i) => (
        <View key={item.key}>
          <Pressable
            disabled={item.disabled}
            onPress={item.onPress}
            style={({ pressed }) => [styles.row, { opacity: pressed ? 0.7 : item.disabled ? 0.5 : 1 }]}
          >
            {item.icon ? <IconChip name={item.icon} tone={item.iconTone ?? 'petrol'} size={32} /> : null}
            <View style={styles.rowText}>
              <Text variant="h2">{item.title}</Text>
              <Text variant="caption" tone="muted">
                {item.subtitle}
              </Text>
            </View>
            {!item.disabled ? (
              <Text variant="h2" tone="terracotta">
                →
              </Text>
            ) : null}
          </Pressable>
          {i < items.length - 1 ? <View style={[styles.divider, { backgroundColor: colors.border }]} /> : null}
        </View>
      ))}
    </Card>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: SPACE.lg, gap: SPACE.md },
  rowText: { flex: 1, gap: 2 },
  divider: { height: StyleSheet.hairlineWidth, marginHorizontal: SPACE.lg },
});
