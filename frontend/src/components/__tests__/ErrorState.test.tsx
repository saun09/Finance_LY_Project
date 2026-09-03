import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react-native';
import { ErrorState } from '../ErrorState';

describe('ErrorState', () => {
  it('renders the normalized error message', async () => {
    await render(<ErrorState message="Could not reach the server." />);
    expect(screen.getByText('Could not reach the server.')).toBeTruthy();
  });

  it('has no retry button when onRetry is not provided', async () => {
    await render(<ErrorState message="Something went wrong." />);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('fires onRetry when the retry button is pressed', async () => {
    const onRetry = jest.fn();
    await render(<ErrorState message="Something went wrong." onRetry={onRetry} />);
    fireEvent.press(screen.getByText('Try again'));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
