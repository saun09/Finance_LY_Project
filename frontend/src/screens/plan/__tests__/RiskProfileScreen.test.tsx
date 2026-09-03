import React from 'react';
import { render, screen } from '@testing-library/react-native';
import { RiskProfileScreen } from '../RiskProfileScreen';
import { useRiskProfileLatest } from '../../../hooks/useRiskProfile';

jest.mock('@react-navigation/native', () => ({
  useNavigation: () => ({ navigate: jest.fn() }),
}));

// Explicit factory so the real hook module (and its AsyncStorage-importing
// DemoUserContext dependency, which needs native module setup Jest doesn't
// provide) is never actually required.
jest.mock('../../../hooks/useRiskProfile', () => ({
  useRiskProfileLatest: jest.fn(),
}));

const mockedUseRiskProfileLatest = useRiskProfileLatest as jest.Mock;

describe('RiskProfileScreen -- capped-risk UI (never hide a cap)', () => {
  it('shows the stated tier, capacity ceiling, and final tier as distinct values when capped', async () => {
    mockedUseRiskProfileLatest.mockReturnValue({
      data: {
        stated_tier: 5,
        capacity_ceiling: 3,
        final_tier: 3,
        capped: true,
        binding_constraints: ['emi_to_income_ratio'],
        unlock_conditions: [
          {
            constraint: 'emi_to_income_ratio',
            message: 'Bring your EMI-to-income ratio below 20% - reduce your monthly EMI outflow by Rs 6,000.',
            current_value: '30.0%',
            target_value: 'below 20%',
          },
        ],
      },
      isPending: false,
      error: null,
      refetch: jest.fn(),
    });

    await render(<RiskProfileScreen />);

    expect(screen.getByText('Tier 5 of 5')).toBeTruthy(); // stated
    expect(screen.getAllByText('Tier 3 of 5').length).toBe(2); // capacity ceiling + final tier, distinctly labeled
    expect(screen.getByText(/Capped by financial capacity, not by your stated tolerance/)).toBeTruthy();
  });

  it('shows the exact unlock-condition wording, current value, and target value from the backend', async () => {
    mockedUseRiskProfileLatest.mockReturnValue({
      data: {
        stated_tier: 5,
        capacity_ceiling: 3,
        final_tier: 3,
        capped: true,
        binding_constraints: ['emi_to_income_ratio'],
        unlock_conditions: [
          {
            constraint: 'emi_to_income_ratio',
            message: 'Bring your EMI-to-income ratio below 20% - reduce your monthly EMI outflow by Rs 6,000.',
            current_value: '30.0%',
            target_value: 'below 20%',
          },
        ],
      },
      isPending: false,
      error: null,
      refetch: jest.fn(),
    });

    await render(<RiskProfileScreen />);

    expect(
      screen.getByText('Bring your EMI-to-income ratio below 20% - reduce your monthly EMI outflow by Rs 6,000.'),
    ).toBeTruthy();
    expect(screen.getByText(/Current: 30.0%/)).toBeTruthy();
    expect(screen.getByText(/Target: below 20%/)).toBeTruthy();
  });

  it('shows a positive, non-capped message and no unlock cards when the tier is not capped', async () => {
    mockedUseRiskProfileLatest.mockReturnValue({
      data: {
        stated_tier: 3,
        capacity_ceiling: 5,
        final_tier: 3,
        capped: false,
        binding_constraints: [],
        unlock_conditions: [],
      },
      isPending: false,
      error: null,
      refetch: jest.fn(),
    });

    await render(<RiskProfileScreen />);

    expect(screen.getByText('No financial-capacity constraint is currently limiting your tier.')).toBeTruthy();
    expect(screen.queryByText('What would raise your tier')).toBeNull();
  });

  it('shows an empty state prompting the questionnaire when no risk profile exists yet (404)', async () => {
    mockedUseRiskProfileLatest.mockReturnValue({
      data: undefined,
      isPending: false,
      error: { status: 404, message: 'not found' },
      refetch: jest.fn(),
    });

    await render(<RiskProfileScreen />);

    expect(screen.getByText("You haven't taken the risk questionnaire yet")).toBeTruthy();
  });
});
