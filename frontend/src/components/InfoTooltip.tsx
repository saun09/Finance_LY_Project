import { Ionicons } from '@expo/vector-icons';
import React, { useState } from 'react';
import { Modal, Pressable, StyleSheet, View } from 'react-native';
import { useAppTheme } from '../theme/ThemeContext';
import { RADIUS, SPACE } from '../theme/tokens';
import { Button } from './Button';
import { Card } from './Card';
import { Text } from './Text';

interface Props {
  title: string;
  description: string;
  /** When given, the trigger renders as this text plus a trailing info
   * icon -- a discreet text link -- instead of a bare icon, for cases
   * where the tooltip itself is the thing being tapped (a footer's "how
   * this works" link) rather than an affordance beside other content. */
  label?: string;
}

/** A small "i" icon (or, with `label`, a discreet text link) that opens a
 * themed modal explaining what a card/step/footer means -- shared so
 * every onboarding screen (and anywhere else) surfaces this consistently
 * instead of an OS-native Alert. */
export function InfoTooltip({ title, description, label }: Props) {
  const { colors } = useAppTheme();
  const [visible, setVisible] = useState(false);

  return (
    <>
      <Pressable
        onPress={() => setVisible(true)}
        hitSlop={10}
        accessibilityRole="button"
        accessibilityLabel={label ?? `About: ${title}`}
        style={label ? styles.labelTrigger : undefined}
      >
        {label ? (
          <Text variant="caption" tone="muted">
            {label}
          </Text>
        ) : null}
        <Ionicons name="information-circle-outline" size={label ? 16 : 22} color={colors.inkFaint} />
      </Pressable>
      <Modal visible={visible} transparent animationType="fade" onRequestClose={() => setVisible(false)}>
        <Pressable style={styles.backdrop} onPress={() => setVisible(false)}>
          <Pressable onPress={(e) => e.stopPropagation()} style={styles.sheetWrap}>
            <Card style={{ backgroundColor: colors.paperRaised }}>
              <View style={styles.header}>
                <Ionicons name="information-circle" size={22} color={colors.terracotta} />
                <Text variant="h2">{title}</Text>
              </View>
              <Text variant="body" tone="muted" style={styles.description}>
                {description}
              </Text>
              <Button label="Got it" variant="secondary" onPress={() => setVisible(false)} />
            </Card>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  labelTrigger: { flexDirection: 'row', alignItems: 'center', gap: SPACE.xs },
  backdrop: { flex: 1, backgroundColor: 'rgba(20, 15, 8, 0.45)', justifyContent: 'center', padding: SPACE.lg },
  sheetWrap: { borderRadius: RADIUS.lg },
  header: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  description: { marginTop: SPACE.sm, marginBottom: SPACE.md },
});
