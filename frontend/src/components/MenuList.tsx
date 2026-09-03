import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useAppTheme } from '../theme/ThemeContext';
import { SPACE } from '../theme/tokens';
import { Card } from './Card';
import { Text } from './Text';

export interface MenuItem {
  key: string;
  title: string;
  subtitle: string;
  onPress: () => void;
  disabled?: boolean;
}

/** A card of tappable rows with a title/subtitle/chevron, each separated
 * by a hairline divider -- the shared shape behind Insights, Transparency,
 * and Profile's own navigation menus. */
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
