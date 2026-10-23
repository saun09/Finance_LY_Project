import { useEffect, useState } from 'react';
import { AccessibilityInfo } from 'react-native';

/** True when the OS/browser has "reduce motion" on (iOS/Android
 * Accessibility settings; the browser's `prefers-reduced-motion` media
 * query on web, which react-native-web's AccessibilityInfo polyfill reads
 * under the hood). Every entrance/count-up animation in the app checks
 * this and, when true, renders its final state immediately instead of
 * animating -- content is never gated behind a skippable animation. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    let mounted = true;
    AccessibilityInfo.isReduceMotionEnabled().then((value) => {
      if (mounted) setReduced(value);
    });
    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduced);
    return () => {
      mounted = false;
      subscription.remove();
    };
  }, []);

  return reduced;
}
