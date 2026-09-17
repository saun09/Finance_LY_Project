import React, { useEffect, useMemo, useRef } from 'react';
import { Animated, Easing, StyleSheet, useWindowDimensions, View } from 'react-native';
import Svg, { Circle, Defs, Path, RadialGradient, Stop} from 'react-native-svg';
import { Text } from './Text';
import { DARK_COLOR, SPACE } from '../theme/tokens';

interface Props {
  onFinish: () => void;
}

/** The ascending path is a fixed cubic bezier -- start low-left, sweep up to
 * high-right -- standing in for "a small nudge moving your money in a
 * better direction" without drawing an actual chart (no axes/gridlines, one
 * stroke, one dot). Kept as plain module constants + a tiny sampler instead
 * of a Lottie file or a motion library: the whole shape is four points, and
 * sampling it ourselves means Animated.Value can drive the dot with plain
 * interpolate() (no react-native-reanimated/redash dependency). */
const VIEW_W = 280;
const VIEW_H = 160;
const P0 = { x: 26, y: 132 };
const P1 = { x: 74, y: 132 };
const P2 = { x: 176, y: 108 };
const P3 = { x: 250, y: 32 };
const SAMPLE_COUNT = 24;

function cubicPoint(t: number) {
  const mt = 1 - t;
  const x = mt ** 3 * P0.x + 3 * mt ** 2 * t * P1.x + 3 * mt * t ** 2 * P2.x + t ** 3 * P3.x;
  const y = mt ** 3 * P0.y + 3 * mt ** 2 * t * P1.y + 3 * mt * t ** 2 * P2.y + t ** 3 * P3.y;
  return { x, y };
}

const SAMPLE_TS = Array.from({ length: SAMPLE_COUNT }, (_, i) => i / (SAMPLE_COUNT - 1));
const SAMPLE_POINTS = SAMPLE_TS.map(cubicPoint);
const PATH_LENGTH = SAMPLE_POINTS.reduce((total, point, i) => {
  if (i === 0) return total;
  const prev = SAMPLE_POINTS[i - 1];
  return total + Math.hypot(point.x - prev.x, point.y - prev.y);
}, 0);
const PATH_D = `M ${P0.x} ${P0.y} C ${P1.x} ${P1.y}, ${P2.x} ${P2.y}, ${P3.x} ${P3.y}`;

// Tangent at the curve's end, used to aim the small arrow that appears once
// the dot arrives -- the "direction" half of the nudge metaphor.
const END_ANGLE_DEG = (Math.atan2(P3.y - P2.y, P3.x - P2.x) * 180) / Math.PI;
const END_TANGENT_LEN = Math.hypot(P3.x - P2.x, P3.y - P2.y);
const ARROW_X = P3.x + ((P3.x - P2.x) / END_TANGENT_LEN) * 10;
const ARROW_Y = P3.y + ((P3.y - P2.y) / END_TANGENT_LEN) * 10;

const AnimatedPath = Animated.createAnimatedComponent(Path);
const AnimatedCircle = Animated.createAnimatedComponent(Circle);

/** Brand splash shown once per app launch, after fonts are ready and before
 * RootNavigator mounts -- see App.tsx's AppShell for how this is sequenced.
 * Deliberately always dark (not tied to useAppTheme/system scheme): this is
 * a fixed brand moment, the same way a logo doesn't repaint itself for
 * light mode, not a regular themed screen. */
export function SplashScreen({ onFinish }: Props) {
  const { width } = useWindowDimensions();
  const illustrationWidth = Math.min(width * 0.62, 240);
  const illustrationHeight = illustrationWidth * (VIEW_H / VIEW_W);

  const glow = useRef(new Animated.Value(0)).current;
  const brand = useRef(new Animated.Value(0)).current;
  const tagline = useRef(new Animated.Value(0)).current;
  const draw = useRef(new Animated.Value(0)).current;
  const arrow = useRef(new Animated.Value(0)).current;
  const screenFade = useRef(new Animated.Value(1)).current;
  const isMounted = useRef(true);

  useEffect(() => {
    return () => {
      isMounted.current = false;
    };
  }, []);

  useEffect(() => {
    Animated.parallel([
      Animated.timing(glow, {
        toValue: 1,
        duration: 700,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
      Animated.sequence([
        Animated.delay(120),
        Animated.timing(brand, {
          toValue: 1,
          duration: 480,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
      ]),
      Animated.sequence([
        Animated.delay(420),
        Animated.timing(tagline, {
          toValue: 1,
          duration: 420,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
      ]),
      Animated.sequence([
        Animated.delay(650),
        Animated.timing(draw, {
          toValue: 1,
          duration: 900,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: false,
        }),
        Animated.timing(arrow, {
          toValue: 1,
          duration: 260,
          easing: Easing.out(Easing.back(1.6)),
          useNativeDriver: true,
        }),
      ]),
    ]).start(() => {
      Animated.sequence([
        Animated.delay(280),
        Animated.timing(screenFade, {
          toValue: 0,
          duration: 320,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
      ]).start(() => {
        if (isMounted.current) onFinish();
      });
    });
  }, [arrow, brand, draw, glow, onFinish, screenFade, tagline]);

  const brandStyle = useMemo(
    () => ({
      opacity: brand,
      transform: [{ translateY: brand.interpolate({ inputRange: [0, 1], outputRange: [14, 0] }) }],
    }),
    [brand]
  );
  const taglineStyle = useMemo(
    () => ({
      opacity: tagline,
      transform: [{ translateY: tagline.interpolate({ inputRange: [0, 1], outputRange: [10, 0] }) }],
    }),
    [tagline]
  );
  const arrowStyle = useMemo(
    () => ({
      opacity: arrow,
      transform: [{ scale: arrow.interpolate({ inputRange: [0, 1], outputRange: [0.4, 1] }) }],
    }),
    [arrow]
  );

  const dashOffset = draw.interpolate({ inputRange: [0, 1], outputRange: [PATH_LENGTH, 0] });
  const dotX = draw.interpolate({ inputRange: SAMPLE_TS, outputRange: SAMPLE_POINTS.map((p) => p.x) });
  const dotY = draw.interpolate({ inputRange: SAMPLE_TS, outputRange: SAMPLE_POINTS.map((p) => p.y) });

  return (
    <View style={styles.container}>
      <Animated.View style={[styles.glow, { opacity: glow }]} pointerEvents="none">
        <Svg width={340} height={340} viewBox="0 0 340 340">
          
            <RadialGradient id="glow" cx="50%" cy="50%" r="50%">
              <Stop offset="0%" stopColor={DARK_COLOR.terracotta} stopOpacity={0.22} />
              <Stop offset="100%" stopColor={DARK_COLOR.terracotta} stopOpacity={0} />
            </RadialGradient>
          
          <Circle cx={170} cy={170} r={170} fill="url(#glow)" />
        </Svg>
      </Animated.View>

      <Animated.View style={[styles.content, { opacity: screenFade }]}>
        <Animated.Text style={[styles.brand, brandStyle]}>Nudge</Animated.Text>
        <Animated.Text style={[styles.tagline, taglineStyle]}>
          Nudge your money in the right direction.
        </Animated.Text>

        <View style={{ width: illustrationWidth, height: illustrationHeight, marginTop: SPACE.xxl }}>
          <Svg width="100%" height="100%" viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}>
            <AnimatedPath
              d={PATH_D}
              stroke={DARK_COLOR.ink}
              strokeOpacity={0.32}
              strokeWidth={2}
              strokeLinecap="round"
              fill="none"
              strokeDasharray={`${PATH_LENGTH}, ${PATH_LENGTH}`}
              strokeDashoffset={dashOffset}
            />
            <AnimatedCircle cx={dotX} cy={dotY} r={5} fill={DARK_COLOR.terracotta} />
            <Animated.View
              style={[
                styles.arrowWrap,
                { left: ARROW_X - 10, top: ARROW_Y - 10, transform: [{ rotate: `${END_ANGLE_DEG}deg` }] },
              ]}
            >
              <Animated.View style={arrowStyle}>
                <Svg width={20} height={20} viewBox="-10 -10 20 20">
                  <Path
                    d="M -6 -6 L 3 0 L -6 6"
                    stroke={DARK_COLOR.terracotta}
                    strokeWidth={2.5}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    fill="none"
                  />
                </Svg>
              </Animated.View>
            </Animated.View>
          </Svg>
        </View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: DARK_COLOR.paper,
  },
  glow: {
    position: 'absolute',
    width: 340,
    height: 340,
  },
  content: {
    alignItems: 'center',
    paddingHorizontal: SPACE.xxl,
  },
  brand: {
    fontFamily: 'Fraunces_600SemiBold',
    fontSize: 46,
    lineHeight: 52,
    color: DARK_COLOR.ink,
    textAlign: 'center',
  },
  tagline: {
    fontFamily: 'IBMPlexSans_400Regular',
    fontSize: 15,
    lineHeight: 22,
    color: DARK_COLOR.inkMuted,
    textAlign: 'center',
    marginTop: SPACE.xs,
    maxWidth: 240,
  },
  arrowWrap: {
    position: 'absolute',
    width: 20,
    height: 20,
  },
});
