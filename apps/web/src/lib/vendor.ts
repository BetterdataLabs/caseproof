export interface VendorCase {
  id: string;
  reference: string;
  title: string;
  invoice: string;
  seller: string;
  buyer: string;
  revision: number;
  research_status?: "pending" | "researching" | "complete" | "failed" | null;
  status: "processing" | "reply_needed" | "bank_review" | "complete" | "closed";
  status_label: string;
  next_step: string;
  created_at: string;
  updated_at: string;
  can_reply: boolean;
  can_upload: boolean;
}

export interface VendorDocument {
  id: string;
  name: string;
  number: string;
  role: string;
  version: number | null;
  state: string;
  active: boolean;
}

export interface VendorMessage {
  id: string;
  direction: "incoming" | "outgoing";
  subject: string;
  sender: string;
  recipient: string;
  created_at: string;
  body: string;
  attachments: VendorDocument[];
}

export interface VendorDetail {
  case: VendorCase;
  bank: string;
  documents: VendorDocument[];
  messages: VendorMessage[];
  client_export: { available: boolean; export_ref: string } | null;
}

export const vendorTone = {
  processing: "blue",
  reply_needed: "amber",
  bank_review: "neutral",
  complete: "teal",
  closed: "neutral",
} as const;
