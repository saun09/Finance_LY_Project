import React, { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import Lottie, { LottieRefCurrentProps } from 'lottie-react';

interface Props {
  source: object;
  loop?: boolean;
  speed?: number;
  size: number;
}

/** Web half of the illustration. lottie-react-native doesn't render on
 * web, so this sibling file (picked up automatically by react-native-web's
 * .web.tsx resolution) swaps in the lottie-web-based player instead, with
 * the same source/loop/speed/size props the native file takes. */
export const LottieIllustration = forwardRef<LottieRefCurrentProps, Props>(
  ({ source, loop = true, speed = 1, size }, ref) => {
    const innerRef = useRef<LottieRefCurrentProps>(null);
    useImperativeHandle(ref, () => innerRef.current as LottieRefCurrentProps);

    useEffect(() => {
      innerRef.current?.setSpeed(speed);
    }, [speed]);

    return (
      <Lottie
        lottieRef={innerRef}
        animationData={source}
        loop={loop}
        autoplay
        style={{ width: size, height: size }}
      />
    );
  }
);
