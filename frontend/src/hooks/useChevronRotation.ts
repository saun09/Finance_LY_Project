import { useEffect, useRef } from 'react';
import { Animated } from 'react-native';
import { useReducedMotion } from './useReducedMotion';

/** A disclosure chevron's rotation, driven purely by the caller's `isOpen`
 * state -- shared by every expand/collapse card (Plan's tier legend,
 * Progress's level/checklist cards, Allocation's methodology disclosure,
 * Leaks' category cards) so the same quick spring rotate-180deg motion
 * means "this expands" everywhere in the app. Spring (not timing) for a
 * slightly livelier settle, tuned to the same speed/bounciness already
 * used for Button's press-scale and the questionnaire's option cards, so
 * every small "springy" motion in the app feels like the same spring.
 * Each caller owns its own open/closed state; this hook only owns the
 * animated value that state drives. */
export function useChevronRotation(isOpen: boolean) {
  const reducedMotion = useReducedMotion();
  const rotation = useRef(new Animated.Value(isOpen ? 1 : 0)).current;
  useEffect(() => {
    if (reducedMotion) {
      rotation.setValue(isOpen ? 1 : 0);
      return;
    }
    Animated.spring(rotation, { toValue: isOpen ? 1 : 0, useNativeDriver: true, speed: 20, bounciness: 6 }).start();
  }, [isOpen, reducedMotion, rotation]);
  return rotation.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '180deg'] });
}
