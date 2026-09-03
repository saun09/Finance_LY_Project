import { AxiosError, AxiosHeaders } from 'axios';
import { API_BASE_URL, ApiError, toApiError } from '../client';

function axiosErrorWithResponse(status: number, data: unknown, code?: string): AxiosError {
  const err = new AxiosError('Request failed', code, undefined, undefined, {
    status,
    statusText: 'error',
    data,
    headers: {},
    config: { headers: new AxiosHeaders() },
  });
  return err;
}

describe('toApiError', () => {
  it('produces a timeout message for ECONNABORTED without touching the network', () => {
    const err = axiosErrorWithResponse(0, undefined, 'ECONNABORTED');
    // Force no response, matching a real timeout (axios never gets one).
    Object.defineProperty(err, 'response', { value: undefined });
    const result = toApiError(err);
    expect(result).toBeInstanceOf(ApiError);
    expect(result.message).toMatch(/took too long/i);
    expect(result.status).toBeNull();
  });

  it('produces a reachability message when there is no response at all', () => {
    const err = axiosErrorWithResponse(0, undefined);
    Object.defineProperty(err, 'response', { value: undefined });
    const result = toApiError(err);
    expect(result.message).toContain(API_BASE_URL);
    expect(result.status).toBeNull();
  });

  it('uses a plain-string detail from an application-raised HTTPException', () => {
    const err = axiosErrorWithResponse(409, { detail: 'Onboarding must be completed first.' });
    const result = toApiError(err);
    expect(result.status).toBe(409);
    expect(result.message).toBe('Onboarding must be completed first.');
  });

  it('flattens a FastAPI automatic-validation detail array into a readable string', () => {
    const err = axiosErrorWithResponse(422, {
      detail: [
        { loc: ['body', 'monthly_income_paise'], msg: 'field required', type: 'missing' },
        { loc: ['body', 'age'], msg: 'ensure this value is greater than 0', type: 'value_error' },
      ],
    });
    const result = toApiError(err);
    expect(result.status).toBe(422);
    expect(result.message).toBe('field required ensure this value is greater than 0');
    expect(result.message).not.toContain('[object Object]');
  });

  it('falls back to a generic message when detail is missing on a 500', () => {
    const err = axiosErrorWithResponse(500, {});
    const result = toApiError(err);
    expect(result.status).toBe(500);
    expect(result.message).toMatch(/went wrong on the server/i);
  });

  it('falls back to a generic message for a non-axios error', () => {
    const result = toApiError(new Error('some unrelated failure'));
    expect(result.message).toMatch(/unexpected error/i);
    expect(result.status).toBeNull();
  });
});
