import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { RADIUS, SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';
import { Text } from './Text';

interface Props {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
  description?: string;
}

/** A labeled boolean row (e.g. "This expense is essential") -- a custom
 * pill switch matching the app's own token palette rather than the
 * platform-default green/blue native Switch. */
export function Toggle({ label, value, onChange, description }: Props) {
  const { colors } = useAppTheme();

  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityState={{ checked: value }}
      onPress={() => onChange(!value)}
      style={styles.row}
    >
      <View style={styles.textCol}>
        <Text variant="bodyMedium">{label}</Text>
        {description ? (
          <Text variant="caption" tone="faint">
            {description}
          </Text>
        ) : null}
      </View>
      <View
        style={[
          styles.track,
          { backgroundColor: value ? colors.terracotta : colors.border },
        ]}
      >
        <View
          style={[
            styles.thumb,
            { backgroundColor: colors.paperRaised, alignSelf: value ? 'flex-end' : 'flex-start' },
          ]}
        />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: SPACE.md },
  textCol: { flex: 1, gap: 2 },
  track: { width: 44, height: 26, borderRadius: RADIUS.pill, padding: 3, justifyContent: 'center' },
  thumb: { width: 20, height: 20, borderRadius: RADIUS.pill },
});
