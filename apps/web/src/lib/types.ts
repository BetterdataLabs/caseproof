// Shapes returned by the CaseProof /v1 API.

export type StatusKey =
  "needs_decision" | "working" | "waiting_customer" | "paused" | "complete" | "manual" | "idle";

export interface SessionInfo {
  user: { id: string; name: string; email: string; title: string };
  organisation: { id: string; name: string; short_name: string };
  roles: string[];
  workspace: "bank" | "vendor" | "viewer";
  memberships: { org_id: string; name: string; roles: string[] }[];
  csrf_token: string;
  environment: string;
  demo_mode: boolean;
  dev_identity: boolean;
  showcase: { reading_case_id: string | null; completed_case_id: string | null };
  model: { name: string; location: string; provider: string };
  counts: { open_tasks: number };
  automation_enabled: boolean;
}

export interface Persona {
  subject: string;
  name: string;
  title: string;
  email: string;
  organisation: string;
  org_short: string;
  roles: string[];
  revoked: boolean;
}

export interface CaseSummary {
  id: string;
  reference: string;
  title: string;
  revision: number;
  lifecycle: string;
  execution: string;
  automation_mode: "off" | "shadow" | "autonomous";
  paused_reason: string | null;
  status: { key: StatusKey; label: string };
  next_action: string;
  next_event_at: string | null;
  seller: string;
  buyer: string;
  invoice_reference: string;
  facility_reference: string;
  assigned_to: { id: string; name: string } | null;
  open_questions: number;
  total_questions: number;
  question_states: { key: string; state: string; result: string }[];
  pending_tasks: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  scenario_key: string;
  etag: string;
}

export interface CaseList {
  items: CaseSummary[];
  counts: Record<string, number>;
  next_cursor: string | null;
}

export interface Fact {
  group?: string;
  field: string;
  value: string;
  quote: string;
  page: number;
  verified: boolean;
}

export interface DocumentChecks {
  enabled: boolean;
  tampering: boolean;
  enabled_by: string | null;
  enabled_at: string | null;
  page_limit: number;
  references: Record<string, { name: string; sha256: string; page_count: number }>;
}

export interface CreditResearch {
  enabled: boolean;
  target?: "buyer" | "seller";
  country?: string;
  requested_at?: string;
  status?: "pending" | "researching" | "complete" | "failed";
  subject?: { name: string; country: string; registration_number: string };
  assessment?: "attention_needed" | "insufficient_information" | "no_material_flags_identified";
  identity?: string;
  summary?: string;
  coverage?: number;
  error?: string;
  limitation?: string;
  completed_at?: string;
  method?: string;
  model?: string;
  information_to_obtain?: string[];
  dimensions?: {
    key: string;
    label: string;
    signal: string;
    analysis: string;
    citations: { evidence_id: string; quote: string; sources: string[] }[];
  }[];
  searches?: {
    angle: number;
    retrieved_at: string;
    queries: string[];
    query_count_estimate: number;
    search_suggestions: string | null;
    sources: { id: string; title: string; url: string }[];
    passages: { id: string; text: string; sources: string[] }[];
  }[];
}

export interface ResearchCase {
  id: string;
  reference: string;
  title: string;
  seller: string;
  buyer: string;
  invoice_reference: string;
  lifecycle: string;
  updated_at: string;
  research: Omit<CreditResearch, "searches" | "dimensions" | "information_to_obtain"> & {
    search_count: number;
    source_count: number;
  };
}

export interface ResearchList {
  items: ResearchCase[];
  counts: Record<string, number>;
  next_cursor: number | null;
}

export interface VisualReview {
  status: "pending" | "review_required" | "no_findings" | "reviewed";
  tampering_requested: boolean;
  template_requested: boolean;
  template_name: string | null;
  template_sha256: string | null;
  template?: "aligned" | "mismatch" | "inconclusive" | "not_requested";
  tampering?: "no_obvious_signs" | "suspicious" | "inconclusive" | "not_requested";
  summary?: string;
  page_count?: number;
  pages_examined?: number;
  limitation: string;
  reviewed_by?: string;
  review_reason?: string;
  findings: {
    kind: string;
    page: number;
    box: number[];
    title: string;
    detail: string;
    origin: string;
  }[];
}

export interface SourceVersion {
  id: string;
  label: string;
  role: string;
  role_label: string;
  version_no: number | null;
  replaces_version_no: number | null;
  state: string;
  is_active: boolean;
  coverage: string;
  reject_code: string | null;
  reject_detail: string;
  duplicate_of: string | null;
  business_event_ref: string | null;
  sha256: string | null;
  size_bytes: number | null;
  page_count: number | null;
  mime: string | null;
  received_via: string;
  created_at: string;
  declared_issuer: string;
  attributed_to: string | null;
  structured: Record<string, unknown> | null;
  text: string | null;
  facts: Fact[];
  has_preview: boolean;
  covered_by_decision_id: string | null;
  visual_review: VisualReview | null;
}

export interface CaseDocument {
  id: string;
  role: string;
  role_label: string;
  number: string;
  title: string;
  active_version_id: string | null;
  versions: SourceVersion[];
}

export interface Question {
  id: string;
  key: string;
  label: string;
  criteria: string;
  state: "open" | "waiting_evidence" | "waiting_decision" | "resolved";
  check_result: string;
  reason_code: string;
  detail: string;
  metrics: Record<string, unknown>;
  evidence: string[];
  resolved_at: string | null;
  resolved_by: string | null;
  resolved_revision: number | null;
}

export interface RequestItem {
  id: string;
  question_key: string;
  question_label: string;
  template_id: string;
  text: string;
  status: string;
  progress_note: string;
}

export interface InfoRequest {
  id: string;
  round: number;
  state: string;
  subject: string;
  body: string;
  recipient: string;
  issued_at: string | null;
  reminder_due_at: string | null;
  reminder_sent_at: string | null;
  stop_due_at: string | null;
  stop_reached_at: string | null;
  created_by: string;
  created_at: string;
  items: RequestItem[];
}

export interface Reply {
  id: string;
  kind: string;
  summary: string;
  sender: string;
  created_at: string;
  request_id: string | null;
  versions: string[];
}

export interface Passage {
  label: string;
  kind: string;
  quote: string;
  version_id?: string;
  attributed_to?: string;
  claim?: string;
  relation?: string;
}

export interface ObservationClaim {
  statement: string;
  quote: string;
  delivery_ref: string | null;
  quantity: string | null;
  unit: string | null;
  time_qualifier: string | null;
  compared_source: string | null;
  source_quote: string | null;
  relation: string;
}

export interface Observation {
  id: string;
  relation: string;
  affected_requirement: string | null;
  summary: string;
  payload: {
    claims?: ObservationClaim[];
    instructions_detected?: boolean;
    missing_context?: string;
    error?: string;
  };
  model: string;
  valid: boolean;
  subject: string | null;
  compared: string[];
  created_at: string;
}

export interface HumanTask {
  id: string;
  kind: string;
  state: string;
  title: string;
  question: string;
  why_stopped: string;
  proposed_action: string;
  requirement_keys: string[];
  source_version_ids: string[];
  source_labels: string[];
  passages: Passage[];
  required_role: string;
  opened_by: string;
  allowed_decisions: { type: string; label: string }[];
  claimed_by: { id: string; name: string } | null;
  claim_expires_at: string | null;
  created_at: string;
  decided_at: string | null;
  observations: Observation[];
  suggested_conditions?: {
    receipt_number?: string;
    delivery_ref?: string;
    claimed_quantity?: string;
  } | null;
  decision: {
    type: string;
    label: string;
    reason: string;
    conditions: Record<string, unknown>;
    actor: string;
    created_at: string;
  } | null;
}

export interface AgentAction {
  seq: number;
  tool: string;
  args: Record<string, unknown>;
  result_code: string;
  result_summary: string;
  reason: string;
  shadow: boolean;
  duration_ms: number;
  created_at: string;
}

export interface AgentRun {
  id: string;
  trigger: string;
  mode: string;
  controller: string;
  model: string;
  outcome: string;
  stop_reason: string;
  summary: string;
  model_calls: number;
  tool_calls: number;
  retries: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: string;
  input_revision: number;
  final_revision: number | null;
  started_at: string;
  ended_at: string | null;
  actions: AgentAction[];
  activity?: {
    review_id: string;
    review_title: string;
    stage: string;
    title: string;
    summary: string;
    state: string;
    continues: boolean;
    cost_known: boolean;
  };
}

export interface ExportRecord {
  id: string;
  export_ref: string;
  state: string;
  case_revision: number;
  policy_label: string;
  created_at: string;
  ready_at: string | null;
  superseded_reason: string | null;
  is_current: boolean;
  pdf_sha256: string | null;
}

export interface AuditEvent {
  id: number;
  event_id: string;
  type: string;
  actor_type: string;
  actor: string;
  summary: string;
  reason: string;
  revision: number | null;
  created_at: string;
  payload: Record<string, unknown>;
}

export interface CaseDetail {
  case: CaseSummary & {
    policy: {
      id: string;
      key: string;
      version: number;
      name: string;
      limits?: Record<string, string | number>;
    };
    seller_detail: Record<string, string>;
    buyer_detail: Record<string, string>;
    receipt_issuers: string[];
    document_checks: DocumentChecks;
    credit_research: CreditResearch;
    vendor_contact: { id: string; name: string } | null;
    budget: {
      wakeups_used: number;
      wakeups_max: number;
      rounds_used: number;
      rounds_max: number;
      cost_reserved_usd: string;
      cost_actual_usd: string;
      budget_usd: string;
    };
    clock_offset_hours: number;
    expires_at: string | null;
    current_export_id: string | null;
  };
  questions: Question[];
  documents: CaseDocument[];
  requests: InfoRequest[];
  replies: Reply[];
  tasks: HumanTask[];
  claims: {
    id: string;
    requirement_key: string;
    statement: string;
    status: string;
    conditions: Record<string, unknown>;
    source: string | null;
    created_at: string;
  }[];
  runs: AgentRun[];
  exports: ExportRecord[];
  timeline: AuditEvent[];
  blockers: { code: string; detail: string; kind?: string }[];
  permissions: {
    decide: boolean;
    supervise: boolean;
    simulate: boolean;
    administer: boolean;
    compose_messages: boolean;
    add_input: boolean;
  };
}

export interface Scenario {
  key: string;
  title: string;
  family: string;
  description: string;
  walkthrough: string[];
  seller: string;
  buyer: string;
  invoice_reference: string;
  initial_documents: number;
}

export interface StagedResponse {
  key: string;
  label: string;
  kind: string;
  sender: string;
  already_sent: boolean;
}

export interface InboxTask {
  id: string;
  kind: string;
  state: string;
  title: string;
  question: string;
  case: { id: string; reference: string; title: string; seller: string };
  required_role: string;
  created_at: string;
  claimed_by: string | null;
}
