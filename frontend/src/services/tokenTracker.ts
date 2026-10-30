import { useState, useEffect } from 'react';

export const INITIAL_TOKEN_QUOTA = 100_000;
const STORAGE_KEY_BALANCE = 'ratio_token_balance';
const STORAGE_KEY_TOTAL_USED = 'ratio_tokens_total_used';
const STORAGE_KEY_LAST_DEDUCTED = 'ratio_tokens_last_deducted';

export interface TokenStats {
  initial: number;
  remaining: number;
  totalUsed: number;
  lastDeducted: number;
  percentRemaining: number;
}

export function getTokenStats(): TokenStats {
  try {
    const rawBal = localStorage.getItem(STORAGE_KEY_BALANCE);
    const rawUsed = localStorage.getItem(STORAGE_KEY_TOTAL_USED);
    const rawLast = localStorage.getItem(STORAGE_KEY_LAST_DEDUCTED);

    const remaining = rawBal !== null ? Math.max(0, parseInt(rawBal, 10)) : INITIAL_TOKEN_QUOTA;
    const totalUsed = rawUsed !== null ? Math.max(0, parseInt(rawUsed, 10)) : 0;
    const lastDeducted = rawLast !== null ? Math.max(0, parseInt(rawLast, 10)) : 0;

    const percentRemaining = Math.max(0, Math.min(100, (remaining / INITIAL_TOKEN_QUOTA) * 100));

    return {
      initial: INITIAL_TOKEN_QUOTA,
      remaining,
      totalUsed,
      lastDeducted,
      percentRemaining,
    };
  } catch {
    return {
      initial: INITIAL_TOKEN_QUOTA,
      remaining: INITIAL_TOKEN_QUOTA,
      totalUsed: 0,
      lastDeducted: 0,
      percentRemaining: 100,
    };
  }
}

export function deductTokens(amount: number): TokenStats {
  const current = getTokenStats();
  const safeDeduct = Math.max(0, Math.round(amount));

  const newRemaining = Math.max(0, current.remaining - safeDeduct);
  const newTotalUsed = current.totalUsed + safeDeduct;

  try {
    localStorage.setItem(STORAGE_KEY_BALANCE, newRemaining.toString());
    localStorage.setItem(STORAGE_KEY_TOTAL_USED, newTotalUsed.toString());
    localStorage.setItem(STORAGE_KEY_LAST_DEDUCTED, safeDeduct.toString());

    window.dispatchEvent(new CustomEvent('ratio_tokens_changed'));
  } catch {
    // ignore local storage write errors
  }

  return getTokenStats();
}

export function resetTokens(): TokenStats {
  try {
    localStorage.setItem(STORAGE_KEY_BALANCE, INITIAL_TOKEN_QUOTA.toString());
    localStorage.setItem(STORAGE_KEY_TOTAL_USED, '0');
    localStorage.setItem(STORAGE_KEY_LAST_DEDUCTED, '0');

    window.dispatchEvent(new CustomEvent('ratio_tokens_changed'));
  } catch {
    // ignore
  }

  return getTokenStats();
}

/**
 * Custom React Hook to subscribe to live token balance changes
 */
export function useTokenTracker(): TokenStats & {
  deduct: (amount: number) => void;
  reset: () => void;
} {
  const [stats, setStats] = useState<TokenStats>(getTokenStats);

  useEffect(() => {
    const handler = () => {
      setStats(getTokenStats());
    };
    window.addEventListener('ratio_tokens_changed', handler);
    window.addEventListener('storage', handler);
    return () => {
      window.removeEventListener('ratio_tokens_changed', handler);
      window.removeEventListener('storage', handler);
    };
  }, []);

  return {
    ...stats,
    deduct: deductTokens,
    reset: resetTokens,
  };
}
