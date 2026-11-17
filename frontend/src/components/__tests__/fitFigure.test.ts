import { fitFigureStyle } from '../fitFigure';

// A half-width metric card on a ~360px phone leaves roughly 120px for the figure.
const HALF_CARD = 120;

describe('fitFigureStyle', () => {
  it('leaves a short figure at its normal size', () => {
    expect(fitFigureStyle('₹5,000', HALF_CARD, 'figureLarge')).toBeUndefined();
  });

  it('shrinks a long rupee figure so every digit fits', () => {
    const text = '-₹24,80,771';
    const style = fitFigureStyle(text, HALF_CARD, 'figureLarge')!;
    expect(style.fontSize).toBeLessThan(28);
    // IBM Plex Mono advances 0.6em per glyph: the whole string must fit
    expect(text.length * 0.6 * (style.fontSize as number)).toBeLessThanOrEqual(HALF_CARD);
  });

  it('fits the personalization adjustment figure', () => {
    const text = '+10.0 pts';
    const style = fitFigureStyle(text, HALF_CARD, 'figureLarge')!;
    expect(text.length * 0.6 * (style.fontSize as number)).toBeLessThanOrEqual(HALF_CARD);
  });

  it('keeps line height in proportion to the new size', () => {
    const style = fitFigureStyle('₹1,24,80,771', HALF_CARD, 'figureLarge')!;
    expect(style.lineHeight).toBe(Math.round((style.fontSize as number) * (32 / 28)));
  });

  it('never goes below a readable minimum', () => {
    expect(fitFigureStyle('₹99,99,99,99,999', 40, 'figureLarge')!.fontSize).toBe(13);
  });

  it('does nothing until the width is known, or for non-monospace text', () => {
    expect(fitFigureStyle('-₹24,80,771', 0, 'figureLarge')).toBeUndefined();
    expect(fitFigureStyle('Tier 3 — Balanced', 60, 'hero')).toBeUndefined();
  });
});
