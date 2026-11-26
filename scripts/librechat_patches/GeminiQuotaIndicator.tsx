import { useEffect, useMemo, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { ContextGauge } from '@librechat/chat/components';
import { useAgentsMapContext } from '~/Providers';

interface GeminiQuotaIndicatorProps {
  endpoint?: string | null;
  model?: string | null;
  agentId?: string | null;
  isSubmitting: boolean;
}

const WINDOW_MS = 60_000;
const STORAGE_PREFIX = 'gemini-local-rpm-v1:';

const MODEL_LIMITS: Record<string, { label: string; rpm: number }> = {
  'gemini-3.5-flash-lite': { label: 'Gemini 3.5 Flash-Lite', rpm: 15 },
  'gemini-3.1-flash-lite': { label: 'Gemini 3.1 Flash-Lite', rpm: 15 },
  'gemini-2.5-flash-lite': { label: 'Gemini 2.5 Flash-Lite', rpm: 10 },
  'gemini-3.6-flash': { label: 'Gemini 3.6 Flash', rpm: 5 },
  'gemini-3.8-flash': { label: 'Gemini 3.8 Flash', rpm: 5 },
};

function normalizeModel(model?: string | null): string {
  return (model ?? '').replace(/^models\//i, '').trim().toLowerCase();
}

function readRecentRequests(key: string, now: number): number[] {
  if (typeof window === 'undefined') {
    return [];
  }
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(key) ?? '[]');
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(
      (timestamp): timestamp is number =>
        typeof timestamp === 'number' &&
        Number.isFinite(timestamp) &&
        timestamp > now - WINDOW_MS &&
        timestamp <= now,
    );
  } catch {
    return [];
  }
}

export default function GeminiQuotaIndicator({
  endpoint,
  model,
  agentId,
  isSubmitting,
}: GeminiQuotaIndicatorProps): ReactElement | null {
  const agentsMap = useAgentsMapContext();
  const marketplaceAgent = endpoint === 'agents' && agentId ? agentsMap?.[agentId] : undefined;
  const effectiveEndpoint = marketplaceAgent?.provider ?? endpoint;
  const effectiveModel = marketplaceAgent?.model ?? model;
  const modelId = normalizeModel(effectiveModel);
  const limit = MODEL_LIMITS[modelId];
  const storageKey = `${STORAGE_PREFIX}${modelId}`;
  const [requestTimes, setRequestTimes] = useState<number[]>([]);
  const [clock, setClock] = useState(() => Date.now());
  const wasSubmitting = useRef(false);

  useEffect(() => {
    const refresh = () => {
      const now = Date.now();
      setClock(now);
      setRequestTimes(readRecentRequests(storageKey, now));
    };
    refresh();
    const timer = window.setInterval(refresh, 1000);
    const onStorage = (event: StorageEvent) => {
      if (event.key === storageKey) {
        refresh();
      }
    };
    window.addEventListener('storage', onStorage);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('storage', onStorage);
    };
  }, [storageKey]);

  useEffect(() => {
    if (
      isSubmitting &&
      !wasSubmitting.current &&
      limit != null &&
      effectiveEndpoint === 'google'
    ) {
      const now = Date.now();
      const recent = readRecentRequests(storageKey, now);
      const next = [...recent, now];
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(next));
      } catch {
        // Keep this indicator best-effort if browser storage is disabled/full.
      }
      setRequestTimes(next);
      setClock(now);
    }
    wasSubmitting.current = isSubmitting;
  }, [effectiveEndpoint, isSubmitting, limit, storageKey]);

  const used = useMemo(
    () => requestTimes.filter((timestamp) => timestamp > clock - WINDOW_MS).length,
    [clock, requestTimes],
  );

  if (effectiveEndpoint !== 'google' || limit == null) {
    return null;
  }

  const percent = Math.min(100, (used / limit.rpm) * 100);
  const tone = percent >= 90 ? 'danger' : percent >= 75 ? 'warning' : 'normal';
  const description = `${limit.label}: ${used} of ${limit.rpm} requests per minute observed in this browser only.`;

  return (
    <span
      role="meter"
      aria-valuemin={0}
      aria-valuemax={limit.rpm}
      aria-valuenow={used}
      aria-label={description}
      title={description}
      className="flex shrink-0 items-center justify-center"
    >
      <ContextGauge percent={percent} indeterminate={false} tone={tone} />
      <span className="sr-only">{description}</span>
    </span>
  );
}
