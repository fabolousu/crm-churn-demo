// CRM domain types — the P0 slice of `crm design/design refs/CRM_Sales_Module_Rebuild_Spec.md`.
// The ML module has its own types in `web/src/lib/types.ts`; the two are deliberately
// separate, exactly as the `crm_` SQL namespace is separate from the ML tables.

export type LeadCategory = "open" | "closed";

export interface LeadStatusDef {
  code: string;
  labelIt: string;
  category: LeadCategory;
  order: number;
  /** Default for a lead created by hand (`Nuovo`). */
  defaultManual?: boolean;
  /** Default for an intake-automation lead (`Interessato`). */
  defaultAuto?: boolean;
  /** Legacy statuses stay selectable but are hidden from new records. */
  legacy?: boolean;
  active: boolean;
}

export interface Owner {
  id: string;
  name: string;
  initials: string;
  role: string;
}

export interface Company {
  id: string;
  name: string;
  macroSector: string;
  sector: string;
  province: string;
  tipologia: string;
  taxCode: string;
  vat: string;
}

export interface Contact {
  id: string;
  fullName: string;
  email: string;
  phone: string;
  /** A contact with one company auto-fills the lead's Azienda; two force a choice. */
  companyIds: string[];
  maturity: "Prospect" | "Lead" | "Cliente";
  privacyConsent: boolean;
}

export interface Initiative {
  id: string;
  code: string;
  name: string;
  referenteId: string;
}

export type ActivityKind = "email" | "call" | "note" | "appointment" | "task";

export interface LeadActivity {
  id: string;
  leadId: string;
  kind: ActivityKind;
  title: string;
  body: string;
  at: string;
  authorId: string;
}

export interface Lead {
  id: string;
  argomento: string;
  descrizione: string;
  requests: string;
  noteMigrate: string;
  contactId: string;
  companyId: string;
  initiativeId: string;
  statusCode: string;
  ownerId: string;
  source: string;
  tipoInteresse: string;
  /** Read-only back-reference to the expression of interest that generated the lead. */
  manifestazioneOrigine: string;
  createdAt: string;
  updatedAt: string;
  closedAt: string | null;
}

/** The seven system views from spec §7.1. */
export type LeadViewId =
  | "personal-open"
  | "all"
  | "open"
  | "closed"
  | "positive"
  | "personal"
  | "personal-closed";

export interface LeadViewDef {
  id: LeadViewId;
  label: string;
  /** Filter applied to the whole lead set. */
  test: (lead: Lead, status: LeadStatusDef, currentUserId: string) => boolean;
}
