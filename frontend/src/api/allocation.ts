import { apiClient } from './client';
import type { AllocationReportOut } from './types';

export const allocationApi = {
  get: (userId: string) => apiClient.get<AllocationReportOut>(`/users/${userId}/allocation`).then((r) => r.data),
};
