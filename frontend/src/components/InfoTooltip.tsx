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
}

/** A small "i" icon that opens a themed modal explaining what a card/step
 * means -- shared so every onboarding screen (and anywhere else) surfaces
 * this consistently instead of an OS-native Alert. */
export function InfoTooltip({ title, description }: Props) {
  const { colors } = useAppTheme();
  const [visible, setVisible] = useState(false);

  return (
    <>
      <Pressable
        onPress={() => setVisible(true)}
        hitSlop={10}
        accessibilityRole="button"
        accessibilityLabel={`About: ${title}`}
      >
        <Ionicons name="information-circle-outline" size={22} color={colors.inkFaint} />
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
  backdrop: { flex: 1, backgroundColor: 'rgba(20, 15, 8, 0.45)', justifyContent: 'center', padding: SPACE.lg },
  sheetWrap: { borderRadius: RADIUS.lg },
  header: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  description: { marginTop: SPACE.sm, marginBottom: SPACE.md },
});
