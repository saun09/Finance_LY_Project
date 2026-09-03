import React from 'react';
import { render, screen } from '@testing-library/react-native';
import { MetricCard } from '../MetricCard';

describe('MetricCard', () => {
  it('renders the label (uppercased), value, and helper text', async () => {
    await render(<MetricCard label="Final tier" value="Tier 3 of 5" helper="Capped by financial capacity" />);
    expect(screen.getByText('FINAL TIER')).toBeTruthy();
    expect(screen.getByText('Tier 3 of 5')).toBeTruthy();
    expect(screen.getByText('Capped by financial capacity')).toBeTruthy();
  });

  it('shows a tone indicator dot for a non-neutral tone (e.g. a capped-tier warning)', async () => {
    await render(<MetricCard label="Final tier" value="Tier 3 of 5" tone="warning" />);
    expect(screen.getByText('●')).toBeTruthy();
  });

  it('shows no tone indicator dot for the default neutral tone', async () => {
    await render(<MetricCard label="Net worth" value="₹1,20,000" />);
    expect(screen.queryByText('●')).toBeNull();
  });

  it('renders without a helper line when none is given', async () => {
    await render(<MetricCard label="EMI-to-income" value="30%" />);
    expect(screen.getByText('30%')).toBeTruthy();
  });
});
