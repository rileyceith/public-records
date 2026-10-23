export type Role = "citizen" | "clerk" | "admin" | "auditor";
export type RecordStatus = "draft" | "pending" | "published" | "archived" | "redacted";
export type AccessLevel = "public" | "restricted" | "confidential";
export type PartyRole = "owner" | "applicant" | "witness" | "official";
export type PartyType = "person" | "company" | "agency";
export type RequestType = "view" | "certified_copy";
export type WorkspaceSection = "home" | "records" | "requests" | "register" | "audit" | "users";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  is_verified: boolean;
  mfa_enabled: boolean;
  agency_id: number | null;
  created_at: string;
}

export interface Agency {
  id: number;
  name: string;
  code: string;
  region: string;
  contact_email: string;
}

export interface RecordType {
  id: number;
  name: string;
  field_schema: Record<string, unknown>;
  default_access: AccessLevel;
  fee: string | number;
}

export interface Attachment {
  id: string;
  original_name: string;
  content_type: string;
  size_bytes: number;
  page_count: number | null;
  checksum_sha256: string;
  is_redacted: boolean;
  created_at: string;
}

export interface Party {
  id: string;
  full_name: string;
  party_type: string;
  address: string;
}

export interface RecordParty {
  id: number;
  role: string;
  party: Party;
}

export interface PartyInput {
  full_name: string;
  party_type: PartyType;
  id_number?: string | null;
  address: string;
  role: PartyRole;
}

export interface PublicRecord {
  id: string;
  record_number: string;
  title: string;
  summary: string;
  record_type: Pick<RecordType, "id" | "name"> & Partial<RecordType>;
  agency: Pick<Agency, "id" | "name" | "code"> & Partial<Agency>;
  status: RecordStatus;
  access_level: AccessLevel;
  date_of_event: string | null;
  date_filed: string | null;
  date_published: string | null;
  last_modified: string;
  created_at: string;
  version: number;
  language: string;
  location_address: string;
  latitude: number | null;
  longitude: number | null;
  tags: string[];
  retention_until: string | null;
  attachments: Attachment[];
  parties: RecordParty[];
  can_access: boolean;
  can_edit: boolean;
}

export interface RecordInput {
  record_number: string;
  title: string;
  summary: string;
  record_type_id: number;
  agency_id: number;
  access_level: AccessLevel | null;
  date_of_event: string | null;
  date_filed: string | null;
  language: string;
  location_address: string;
  latitude: number | null;
  longitude: number | null;
  tags: string[];
  retention_until: string | null;
}

export interface AccessRequest {
  id: string;
  record_id: string;
  record_number: string;
  record_title: string;
  requester_id: number;
  requester_email: string;
  request_type: RequestType;
  purpose: string;
  status: "pending" | "approved" | "denied";
  fee_amount: string | number;
  payment_status: string;
  decided_by_id: number | null;
  decision_reason: string;
  requested_at: string;
  decided_at: string | null;
}

export interface UserCreateInput {
  email: string;
  full_name: string;
  password: string;
  role: Role;
  agency_id: number | null;
  is_verified: boolean;
}

export interface UserUpdateInput {
  role?: Role;
  is_active?: boolean;
  is_verified?: boolean;
  agency_id?: number | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditEvent {
  id: number;
  actor_id: number | null;
  actor_email: string;
  action: string;
  entity_type: string;
  entity_id: string;
  record_id: string | null;
  ip_address: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface LoginResult {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}
