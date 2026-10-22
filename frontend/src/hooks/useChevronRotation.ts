import { useEffect, useRef } from 'react';
import { Animated } from 'react-native';
import { useReducedMotion } from './useReducedMotion';

/** A disclosure chevron's rotation, driven purely by the caller's `isOpen`
 * state -- shared by every expand/collapse card (Plan's tier legend,
 * Progress's level/checklist cards, Allocation's methodology disclosure)
 * so the same ~200ms rotate-180deg motion means "this expands" everywhere
 * in the app. Each caller owns its own open/closed state; this hook only
 * owns the animated value that state drives. */
export function useChevronRotation(isOpen: boolean) {
  const reducedMotion = useReducedMotion();
  const rotation = useRef(new Animated.Value(isOpen ? 1 : 0)).current;
  useEffect(() => {
    Animated.timing(rotation, {
      toValue: isOpen ? 1 : 0,
      duration: reducedMotion ? 0 : 200,
      useNativeDriver: true,
    }).start();
  }, [isOpen, reducedMotion, rotation]);
  return rotation.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '180deg'] });
}
