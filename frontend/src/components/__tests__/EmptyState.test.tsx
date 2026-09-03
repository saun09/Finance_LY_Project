import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react-native';
import { EmptyState } from '../EmptyState';

describe('EmptyState', () => {
  it('renders the title and message', async () => {
    await render(<EmptyState title="No history yet" message="Your timeline will appear here." />);
    expect(screen.getByText('No history yet')).toBeTruthy();
    expect(screen.getByText('Your timeline will appear here.')).toBeTruthy();
  });

  it('does not render an action button when no actionLabel/onAction is given', async () => {
    await render(<EmptyState title="Nothing here" message="Nothing to see." />);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('renders and fires the action button only when both actionLabel and onAction are given', async () => {
    const onAction = jest.fn();
    await render(<EmptyState title="No policies" message="Add one below." actionLabel="Add now" onAction={onAction} />);
    const button = screen.getByRole('button');
    expect(button).toBeTruthy();
    fireEvent.press(button);
    expect(onAction).toHaveBeenCalledTimes(1);
  });
});
