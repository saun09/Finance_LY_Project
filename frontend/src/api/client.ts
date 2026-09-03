import axios, { AxiosError } from 'axios';
import { Platform } from 'react-native';
import type { ApiErrorBody } from './types';

/**
 * Base URL resolution (Section 26/27 — no secrets here, no auth to fake):
 * - Set EXPO_PUBLIC_API_BASE_URL in .env (or app config) to point at
 *   wherever `uvicorn app.main:app` is actually running.
 * - Fallbacks below exist only so a fresh checkout runs against a local
 *   `uvicorn app.main:app --host 0.0.0.0 --reload` without any setup:
 *   the Android emulator can't reach the host machine via `localhost` --
 *   it needs the special alias 10.0.2.2 -- while a physical device on the
 *   same Wi-Fi needs the host's real LAN IP, which can't be guessed here.
 */
const DEFAULT_BASE_URL = Platform.select({
  android: 'http://10.0.2.2:8000',
  default: 'http://127.0.0.1:8000',
});

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? DEFAULT_BASE_URL;

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

/** A single, human-readable message for any failure mode the backend or
 * network can produce -- screens should never render a raw Python
 * traceback or a bare axios error. */
export class ApiError extends Error {
  status: number | null;
  constructor(message: string, status: number | null) {
    super(message);
    this.status = status;
  }
}

/** `detail` is a plain string for app-raised HTTPExceptions, but an array
 * of {loc, msg, type} for FastAPI's own automatic request-validation 422s
 * -- normalize both into one human-readable string. */
function detailToMessage(detail: ApiErrorBody['detail'] | undefined): string | null {
  if (detail === undefined || detail === null) return null;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((d) => d.msg).join(' ');
  }
  return null;
}

export function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const err = error as AxiosError<ApiErrorBody>;
    if (err.code === 'ECONNABORTED') {
      return new ApiError('The request took too long to respond. Please try again.', null);
    }
    if (!err.response) {
      return new ApiError(
        `Could not reach the server at ${API_BASE_URL}. Check that the backend is running and reachable.`,
        null,
      );
    }
    const status = err.response.status;
    const detail = detailToMessage(err.response.data?.detail);
    if (status === 404) return new ApiError(detail ?? 'The requested information was not found.', 404);
    if (status === 409) return new ApiError(detail ?? 'This isn’t ready yet — an earlier step needs to be completed first.', 409);
    if (status === 422) return new ApiError(detail ?? 'Some of the information provided was invalid.', 422);
    if (status >= 500) return new ApiError('Something went wrong on the server. Please try again shortly.', status);
    return new ApiError(detail ?? 'Something went wrong.', status);
  }
  return new ApiError('An unexpected error occurred.', null);
}
