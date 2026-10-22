import React from 'react';
import { StyleSheet, View } from 'react-native';
import { useAppTheme } from '../theme/ThemeContext';
import { Text } from './Text';

export function initialsFrom(fullName: string | null | undefined, username: string | null): string {
  const source = (fullName?.trim() || username || '').trim();
  if (!source) return '?';
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

/** A circular initials badge -- the app's one "avatar" affordance (there's
 * no photo upload anywhere in the backend), shared between the Profile
 * hero card and the Home header so the same name always renders the same
 * initials in the same two tones everywhere. */
export function AvatarBadge({ initials, size = 56 }: { initials: string; size?: number }) {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.avatar, { width: size, height: size, borderRadius: size / 2, backgroundColor: colors.terracottaSoft }]}>
      <Text variant="h2" tone="terracotta" style={{ fontSize: Math.round(size * 0.34), lineHeight: Math.round(size * 0.4) }}>
        {initials}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  avatar: { alignItems: 'center', justifyContent: 'center' },
});
