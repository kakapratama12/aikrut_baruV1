import { useAuth } from '../context/AuthContext';

/**
 * Hook to refresh user credits after AI operations complete
 * Usage: const refreshCredits = useCreditsRefresh();
 *        await someAIOperation();
 *        await refreshCredits();
 */
export const useCreditsRefresh = () => {
  const { refreshUser } = useAuth();
  
  return async () => {
    // Small delay to ensure backend has updated the database
    await new Promise(resolve => setTimeout(resolve, 500));
    await refreshUser();
  };
};
