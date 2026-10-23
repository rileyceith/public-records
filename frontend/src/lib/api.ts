import type {
  AccessRequest,
  Agency,
  Attachment,
  AuditEvent,
  LoginResult,
  Page,
  PartyInput,
  PublicRecord,
  RecordInput,
  RecordType,
  RequestType,
  User,
  UserCreateInput,
  UserUpdateInput,
} from "./types";

const enc = encodeURIComponent;

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...init, headers, credentials: "same-origin" });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const message =
      typeof payload === "object" && payload !== null && "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : `Request failed (${response.status}).`;
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; service: string }>("/api/health"),
  login: (email: string, password: string) =>
    request<LoginResult>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  listRecords: (params: URLSearchParams, signal?: AbortSignal) =>
    request<Page<PublicRecord>>(`/api/records?${params.toString()}`, { signal }),
  register: (payload: { email: string; full_name: string; password: string }) =>
    request<User>("/api/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  listAgencies: () => request<Agency[]>("/api/agencies"),
  listRecordTypes: () => request<RecordType[]>("/api/record-types"),
  suggest: (prefix: string, signal?: AbortSignal) =>
    request<{ suggestions: string[] }>(`/api/records/suggest?prefix=${enc(prefix)}`, { signal }),
  recordAction: (id: string, action: "submit" | "publish" | "archive") =>
    request<PublicRecord>(`/api/records/${enc(id)}/${action}`, { method: "POST" }),
  redactRecord: (id: string, fields: string[], attachmentIds: string[]) =>
    request<PublicRecord>(`/api/records/${enc(id)}/redact`, {
      method: "POST",
      body: JSON.stringify({ fields, attachment_ids: attachmentIds }),
    }),
  addParty: (id: string, party: PartyInput) =>
    request<PublicRecord>(`/api/records/${enc(id)}/parties`, { method: "POST", body: JSON.stringify(party) }),
  removeParty: (id: string, linkId: number) =>
    request<PublicRecord>(`/api/records/${enc(id)}/parties/${linkId}`, { method: "DELETE" }),
  runOcr: (attachmentId: string) =>
    request<Attachment>(`/api/attachments/${enc(attachmentId)}/ocr`, { method: "POST" }),
  listAccessRequests: (status?: string) =>
    request<AccessRequest[]>(`/api/access-requests${status ? `?status=${enc(status)}` : ""}`),
  createAccessRequest: (payload: { record_id: string; request_type: RequestType; purpose: string }) =>
    request<AccessRequest>("/api/access-requests", { method: "POST", body: JSON.stringify(payload) }),
  approveAccessRequest: (id: string, reason: string) =>
    request<AccessRequest>(`/api/access-requests/${enc(id)}/approve`, { method: "POST", body: JSON.stringify({ reason }) }),
  denyAccessRequest: (id: string, reason: string) =>
    request<AccessRequest>(`/api/access-requests/${enc(id)}/deny`, { method: "POST", body: JSON.stringify({ reason }) }),
  markAccessRequestPaid: (id: string) =>
    request<AccessRequest>(`/api/access-requests/${enc(id)}/mark-paid`, { method: "POST" }),
  updateUser: (id: number, payload: UserUpdateInput) =>
    request<User>(`/api/auth/users/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  getRecord: (id: string) => request<PublicRecord>(`/api/records/${encodeURIComponent(id)}`),
  createRecord: (record: RecordInput) =>
    request<PublicRecord>("/api/records", { method: "POST", body: JSON.stringify(record) }),
  updateRecord: (id: string, record: RecordInput) =>
    request<PublicRecord>(`/api/records/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(record),
    }),
  deleteRecord: (id: string) =>
    request<void>(`/api/records/${encodeURIComponent(id)}`, { method: "DELETE" }),
  createUser: (payload: UserCreateInput) =>
    request<User>("/api/auth/users", { method: "POST", body: JSON.stringify(payload) }),
  listUsers: () => request<User[]>("/api/auth/users"),
  listAuditEvents: (params: URLSearchParams, signal?: AbortSignal) =>
    request<Page<AuditEvent>>(`/api/audit?${params.toString()}`, { signal }),
  uploadAttachment: (recordId: string, file: File) => {
    const form = new FormData();
    form.set("file", file);
    return request<Attachment>(`/api/records/${encodeURIComponent(recordId)}/attachments`, {
      method: "POST",
      body: form,
    });
  },
  deleteAttachment: (id: string) =>
    request<void>(`/api/attachments/${encodeURIComponent(id)}`, { method: "DELETE" }),
  downloadAttachment: async (attachment: Attachment): Promise<void> => {
    const response = await fetch(`/api/attachments/${encodeURIComponent(attachment.id)}/download`, {
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
      credentials: "same-origin",
    });
    if (!response.ok) {
      throw new ApiError("Unable to download this file.", response.status);
    }
    const objectUrl = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = attachment.original_name;
    link.click();
    URL.revokeObjectURL(objectUrl);
  },
};
