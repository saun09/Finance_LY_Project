import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import React from 'react';
import { Pressable, StyleSheet } from 'react-native';
import { useAppTheme } from '../theme/ThemeContext';
import { Text } from './Text';

interface Props {
  label?: string;
}

/** Every stack in this app hides its native header (headerShown: false, so
 * the shared design system controls the whole screen), which otherwise
 * leaves sub-screens with no way back except an OS back gesture. This is
 * the in-app back affordance for those screens. */
export function BackHeader({ label = 'Back' }: Props) {
  const navigation = useNavigation();
  const { colors } = useAppTheme();

  return (
    <Pressable
      onPress={() => navigation.goBack()}
      style={styles.row}
      hitSlop={10}
      accessibilityRole="button"
      accessibilityLabel="Go back"
    >
      <Ionicons name="chevron-back" size={18} color={colors.terracotta} />
      <Text variant="label" tone="terracotta">
        {label.toUpperCase()}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 2, alignSelf: 'flex-start' },
});
