import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useAppTheme } from '../theme/ThemeContext';
import { RADIUS, SPACE } from '../theme/tokens';
import { Text } from './Text';

interface Props {
  visible: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

/** A bottom slide-over drawer for an "add X" form -- replaces a form that
 * previously lived inline at the end of a list, so the list itself reads
 * as the screen's content and adding something is a deliberate, separate
 * action instead of a form that's always on-screen taking up space.
 * Same backdrop/dismiss pattern as InfoTooltip's modal, anchored to the
 * bottom and capped at 85% height with its own scroll for a tall form. */
export function FormSheet({ visible, onClose, title, children }: Props) {
  const { colors } = useAppTheme();

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable onPress={(e) => e.stopPropagation()} style={[styles.sheet, { backgroundColor: colors.paperRaised, borderColor: colors.border }]}>
          <View style={styles.header}>
            <Text variant="h2">{title}</Text>
            <Pressable onPress={onClose} hitSlop={10} accessibilityRole="button" accessibilityLabel="Close">
              <Ionicons name="close" size={22} color={colors.inkFaint} />
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
            {children}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(20, 15, 8, 0.55)', justifyContent: 'flex-end' },
  sheet: {
    maxHeight: '85%',
    borderTopLeftRadius: RADIUS.lg,
    borderTopRightRadius: RADIUS.lg,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderBottomWidth: 0,
    paddingTop: SPACE.lg,
    paddingHorizontal: SPACE.lg,
  },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: SPACE.md },
  body: { gap: SPACE.md, paddingBottom: SPACE.xl },
});
