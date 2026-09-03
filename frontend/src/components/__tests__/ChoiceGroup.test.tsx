import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react-native';
import { ChoiceGroup } from '../ChoiceGroup';

const OPTIONS = [
  { value: 'regular', label: 'Regular' },
  { value: 'irregular', label: 'Irregular' },
];

describe('ChoiceGroup', () => {
  it('renders every option label', async () => {
    await render(<ChoiceGroup label="Income stability" options={OPTIONS} value={null} onChange={jest.fn()} />);
    expect(screen.getByText('Regular')).toBeTruthy();
    expect(screen.getByText('Irregular')).toBeTruthy();
  });

  it('calls onChange with the pressed option\'s value, not the currently selected one', async () => {
    const onChange = jest.fn();
    await render(<ChoiceGroup label="Income stability" options={OPTIONS} value="regular" onChange={onChange} />);
    fireEvent.press(screen.getByText('Irregular'));
    expect(onChange).toHaveBeenCalledWith('irregular');
    expect(onChange).not.toHaveBeenCalledWith('regular');
  });

  it('marks the currently selected option as selected for accessibility', async () => {
    await render(<ChoiceGroup label="Income stability" options={OPTIONS} value="irregular" onChange={jest.fn()} />);
    expect(screen.getByRole('button', { name: 'Irregular', selected: true })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Regular', selected: false })).toBeTruthy();
  });

  it('renders the question text as a normal heading, not an all-caps field label, when uppercaseLabel is false', async () => {
    await render(
      <ChoiceGroup label="How would you react?" uppercaseLabel={false} options={OPTIONS} value={null} onChange={jest.fn()} />,
    );
    expect(screen.getByText('How would you react?')).toBeTruthy();
    expect(screen.queryByText('HOW WOULD YOU REACT?')).toBeNull();
  });
});
