import React, { forwardRef } from 'react';
import LottieView, { AnimationObject } from 'lottie-react-native';

interface Props {
  source: AnimationObject;
  loop?: boolean;
  speed?: number;
  size: number;
}

/** Native (iOS/Android) half of the illustration. Paired with
 * LottieIllustration.web.tsx -- Metro and react-native-web resolve the
 * right one per platform from the .native.tsx / .web.tsx suffix, so
 * SplashScreen just imports './LottieIllustration' and never has to
 * branch on Platform.OS itself. Same reasoning as the interpolateLinear
 * helper this replaces: native-only APIs (here, lottie-react-native's
 * player) don't survive being reached from web, so the split happens at
 * the file level instead of inside one component. */
export const LottieIllustration = forwardRef<LottieView, Props>(
  ({ source, loop = true, speed = 1, size }, ref) => (
    <LottieView
      ref={ref}
      source={source}
      autoPlay
      loop={loop}
      speed={speed}
      style={{ width: size, height: size }}
    />
  )
);
