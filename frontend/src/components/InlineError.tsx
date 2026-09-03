import React from 'react';
import { useAppTheme } from '../theme/ThemeContext';
import { Card } from './Card';
import { Text } from './Text';

/** A soft danger-toned card for inline form/submit errors -- shared so
 * every onboarding screen renders API/validation failures identically. */
export function InlineError({ message }: { message: string }) {
  const { colors } = useAppTheme();
  return (
    <Card style={{ backgroundColor: colors.dangerSoft, borderColor: colors.dangerSoft }}>
      <Text variant="bodyMedium" tone="danger">
        {message}
      </Text>
    </Card>
  );
}
