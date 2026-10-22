import { ASSET_CLASSES, type AssetClass } from '../api/types';

/** Set equity to `equityPct` and rescale the other four classes in
 * proportion to their current weights, so the mix still adds up to exactly
 * 100 (to the cent). Mirrors how the backend applies the personalization
 * offset, so "set my own mix" behaves the way the plan itself moves.
 *
 * Works in integer hundredths to avoid float drift; any rounding residual
 * goes to the largest non-equity class, never to equity -- the number the
 * user actually chose stays exactly what they chose. */
export function mixWithEquity(base: Record<AssetClass, string>, equityPct: number): Record<AssetClass, string> {
  const equityCents = Math.round(Math.min(100, Math.max(0, equityPct)) * 100);
  const others = ASSET_CLASSES.filter((ac) => ac !== 'equity');
  const othersTotal = others.reduce((sum, ac) => sum + Number(base[ac] ?? 0), 0);
  const pool = 10000 - equityCents;

  const cents: Record<AssetClass, number> = { cash: 0, debt: 0, equity: equityCents, real_assets: 0, alternatives: 0 };
  for (const ac of others) {
    const share = othersTotal > 0 ? Number(base[ac] ?? 0) / othersTotal : 1 / others.length;
    cents[ac] = Math.round(pool * share);
  }
  const residual = 10000 - ASSET_CLASSES.reduce((sum, ac) => sum + cents[ac], 0);
  if (residual !== 0) {
    const largest = others.reduce((a, b) => (cents[b] > cents[a] ? b : a));
    cents[largest] += residual;
  }

  const out = {} as Record<AssetClass, string>;
  for (const ac of ASSET_CLASSES) out[ac] = (cents[ac] / 100).toFixed(2);
  return out;
}
