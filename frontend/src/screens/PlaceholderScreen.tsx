import React from 'react';
import { ScreenContainer } from '../components/ScreenContainer';
import { Text } from '../components/Text';
import { Card } from '../components/Card';

/** Every screen not yet built in the current phase renders this instead
 * of being silently missing from navigation -- so the full app shell is
 * always demonstrable end-to-end, and it's obvious what's still coming
 * rather than a blank/crashing screen. Replaced screen-by-screen in
 * later phases (see the master prompt's own phase breakdown). */
export function PlaceholderScreen({ title, phase }: { title: string; phase: string }) {
  return (
    <ScreenContainer>
      <Text variant="display">{title}</Text>
      <Card>
        <Text variant="bodyMedium" tone="muted">
          Built in {phase}.
        </Text>
      </Card>
    </ScreenContainer>
  );
}
