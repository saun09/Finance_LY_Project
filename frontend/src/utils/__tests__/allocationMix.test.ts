import type { AssetClass } from '../../api/types';
import { mixWithEquity } from '../allocationMix';

const TIER1: Record<AssetClass, string> = {
  cash: '30.00',
  debt: '50.00',
  equity: '15.00',
  real_assets: '5.00',
  alternatives: '0.00',
};

const total = (mix: Record<AssetClass, string>) =>
  Object.values(mix).reduce((sum, v) => sum + Math.round(Number(v) * 100), 0);

describe('mixWithEquity', () => {
  it('sets equity exactly and keeps the mix at 100', () => {
    const mix = mixWithEquity(TIER1, 21);
    expect(mix.equity).toBe('21.00');
    expect(total(mix)).toBe(10000);
  });

  it('rescales the other classes in proportion to their weights', () => {
    const mix = mixWithEquity(TIER1, 25);
    // the other 75 points split 30:50:5:0 (out of 85)
    expect(Number(mix.cash)).toBeCloseTo(26.47, 2);
    expect(Number(mix.debt)).toBeCloseTo(44.12, 2);
    expect(mix.alternatives).toBe('0.00');
  });

  it('never lets rounding move the chosen equity', () => {
    for (const equity of [0, 7, 33, 66.5, 99, 100]) {
      const mix = mixWithEquity(TIER1, equity);
      expect(Number(mix.equity)).toBe(equity);
      expect(total(mix)).toBe(10000);
    }
  });

  it('clamps out-of-range equity to 0..100', () => {
    expect(mixWithEquity(TIER1, 120).equity).toBe('100.00');
    expect(mixWithEquity(TIER1, -5).equity).toBe('0.00');
  });
});
