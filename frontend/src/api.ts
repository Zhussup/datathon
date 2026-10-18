export type ApiOptions = { baseUrl: string; apiKey: string };

export type EvidenceFrame = { timestamp_sec: number; image_base64: string };

export type Violation = {
  type: string;
  timecode_sec: number;
  description: string;
  evidence_frames: EvidenceFrame[];
  npa?: string;
  rule_id?: string;
};

export type JobResult = {
  verdict: "no_violation" | "violation";
  violations: Violation[];
};

export type Job = {
  job_id: string;
  status: "processing" | "done" | "failed";
  error?: string;
} & Partial<JobResult>;

// Ключ задаётся при сборке (VITE_API_KEY) или в localStorage("forte-api-key").
// Пока ключа нет — интерфейс работает в демо-режиме, файл никуда не уходит.
export function apiOptions(): ApiOptions | null {
  let apiKey = import.meta.env.VITE_API_KEY;
  if (!apiKey) {
    try {
      apiKey = localStorage.getItem("forte-api-key") ?? "";
    } catch {
      /* localStorage может быть запрещён — остаёмся в демо-режиме. */
    }
  }
  if (!apiKey) return null;
  return { baseUrl: import.meta.env.VITE_API_BASE ?? "", apiKey };
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function uploadForAnalysis(
  file: File,
  opts: ApiOptions,
  signal?: AbortSignal,
): Promise<string> {
  const form = new FormData();
  form.append("file", file, file.name);
  const response = await fetch(`${opts.baseUrl}/api/v1/analyze`, {
    method: "POST",
    headers: opts.apiKey ? { "X-API-Key": opts.apiKey } : undefined,
    body: form,
    signal,
  });
  if (!response.ok) {
    if (response.status === 401) {
      throw new ApiError(401, "Ключ отклонён сервисом (HTTP 401).");
    }
    throw new ApiError(response.status, `Сервис отклонил загрузку (HTTP ${response.status})`);
  }
  const data = (await response.json()) as { job_id?: string };
  if (!data.job_id) throw new Error("Сервис не вернул идентификатор задачи");
  return data.job_id;
}

// Опрос задачи до финального статуса; лимит FAQ 14 — 5 минут, даём ещё минуту сверху.
export async function awaitJob(
  jobId: string,
  opts: ApiOptions,
  signal?: AbortSignal,
): Promise<Job> {
  const started = performance.now();
  for (;;) {
    if (performance.now() - started > 330_000) {
      throw new Error("Сервис не успел обработать видео (лимит 5 минут).");
    }
    const response = await fetch(`${opts.baseUrl}/api/v1/jobs/${jobId}`, {
      headers: opts.apiKey ? { "X-API-Key": opts.apiKey } : undefined,
      signal,
    });
    if (!response.ok) {
      if (response.status === 401) {
        throw new ApiError(401, "Ключ отклонён сервисом (HTTP 401).");
      }
      throw new ApiError(response.status, `Сервис не вернул статус задачи (HTTP ${response.status})`);
    }
    const job = (await response.json()) as Job;
    if (job.status !== "processing") return job;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}