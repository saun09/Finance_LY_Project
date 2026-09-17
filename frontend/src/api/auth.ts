import { apiClient } from './client';
import type { AuthUserOut, LoginIn, SignupIn } from './types';

/** POST /auth/signup and /auth/login -- real, password-checked account
 * creation and sign-in (see backend/app/services/auth_service.py). This
 * only gates entry into the app; every other endpoint still trusts the
 * user_id in its URL path exactly as before, unchanged by this. */
export const authApi = {
  signup: (body: SignupIn) => apiClient.post<AuthUserOut>('/auth/signup', body).then((r) => r.data),

  login: (body: LoginIn) => apiClient.post<AuthUserOut>('/auth/login', body).then((r) => r.data),
};
