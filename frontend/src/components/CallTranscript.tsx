import React from 'react';
import { StyleSheet, View } from 'react-native';
import type { NudgeRole } from '../api/types';
import { useAppTheme } from '../theme/ThemeContext';
import { RADIUS, SPACE } from '../theme/tokens';
import { Text } from './Text';

export interface TranscriptLine {
  id: string;
  role: NudgeRole;
  text: string;
}

/** A Nudge call as chat bubbles -- the user's lines on the right, Nudge's
 * on the left. Shared by the live call sheet and the saved-call screen so a
 * transcript reads the same during the call and afterwards. `pendingLabel`
 * adds a faint trailing line ("Listening…") while a live call is waiting
 * on the next turn. */
export function CallTranscript({ lines, pendingLabel }: { lines: TranscriptLine[]; pendingLabel?: string | null }) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.list}>
      {lines.map((line) => {
        const mine = line.role === 'user';
        return (
          <View key={line.id} style={[styles.row, mine ? styles.rowMine : styles.rowTheirs]}>
            <Text variant="caption" tone="faint">
              {mine ? 'You' : 'Nudge'}
            </Text>
            <View
              style={[
                styles.bubble,
                mine
                  ? { backgroundColor: colors.terracottaSoft, borderBottomRightRadius: RADIUS.sm }
                  : { backgroundColor: colors.paperSunken, borderBottomLeftRadius: RADIUS.sm },
              ]}
            >
              <Text variant="body">{line.text}</Text>
            </View>
          </View>
        );
      })}
      {pendingLabel ? (
        <Text variant="caption" tone="faint" style={styles.pending}>
          {pendingLabel}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  list: { gap: SPACE.md },
  row: { gap: 4, maxWidth: '86%' },
  rowMine: { alignSelf: 'flex-end', alignItems: 'flex-end' },
  rowTheirs: { alignSelf: 'flex-start', alignItems: 'flex-start' },
  bubble: { borderRadius: RADIUS.md, paddingHorizontal: SPACE.md, paddingVertical: SPACE.sm },
  pending: { alignSelf: 'center', fontStyle: 'italic' },
});
