// In-memory CRM state with localStorage persistence.
//
// This is the demo's data layer: it mirrors the `crm_` tables so the screens behave like
// the specified product (save states, status hooks, uniqueness, reassignment) without a
// backend. Swapping it for `api/crm` later is a change of this file only.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type {
  Company,
  Contact,
  Initiative,
  Lead,
  LeadActivity,
  LeadStatusDef,
  Owner,
} from "./types";
import {
  ACTIVITIES,
  COMPANIES,
  CONTACTS,
  CURRENT_USER_ID,
  INITIATIVES,
  LEADS,
  OWNERS,
  STATUSES,
} from "./seed";

const STORAGE_KEY = "iniziativa-crm-v2";

function seedLeads(): Lead[] {
  return LEADS.map((lead) => ({ ...lead }));
}

function seedActivities(): LeadActivity[] {
  return ACTIVITIES.map((activity) => ({ ...activity }));
}

function loadLeads(): Lead[] {
  if (typeof window === "undefined") return seedLeads();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return seedLeads();
    const parsed = JSON.parse(raw) as { leads?: Lead[] };
    return Array.isArray(parsed.leads) && parsed.leads.length > 0
      ? parsed.leads
      : seedLeads();
  } catch {
    return seedLeads();
  }
}

function loadActivities(): LeadActivity[] {
  if (typeof window === "undefined") return seedActivities();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return seedActivities();
    const parsed = JSON.parse(raw) as { activities?: LeadActivity[] };
    return Array.isArray(parsed.activities) ? parsed.activities : seedActivities();
  } catch {
    return seedActivities();
  }
}

function nowIso(): string {
  return new Date().toISOString();
}

export interface CrmContextValue {
  leads: Lead[];
  activities: LeadActivity[];
  statuses: LeadStatusDef[];
  owners: Owner[];
  companies: Company[];
  contacts: Contact[];
  initiatives: Initiative[];
  currentUserId: string;
  currentUser: Owner;
  statusByCode: (code: string) => LeadStatusDef;
  companyById: (id: string) => Company | undefined;
  contactById: (id: string) => Contact | undefined;
  initiativeById: (id: string) => Initiative | undefined;
  ownerById: (id: string) => Owner | undefined;
  /** Contacts with exactly one company auto-fill the lead's Azienda (P0 C15). */
  companiesForContact: (contactId: string) => Company[];
  /** (Contatto, Anagrafica interesse) uniqueness check (P0 C14). */
  findDuplicate: (
    contactId: string,
    initiativeId: string,
    exceptLeadId?: string,
  ) => Lead | undefined;
  saveLead: (lead: Lead) => Lead;
  createLead: (
    draft: Omit<Lead, "createdAt" | "updatedAt" | "closedAt">,
  ) => Lead;
  bulkSetStatus: (ids: string[], statusCode: string) => void;
  bulkSetOwner: (ids: string[], ownerId: string) => void;
  resetDemo: () => void;
}

const CrmContext = createContext<CrmContextValue | null>(null);

export function CrmProvider({ children }: { children: ReactNode }) {
  const [leads, setLeads] = useState<Lead[]>(loadLeads);
  const [activities, setActivities] = useState<LeadActivity[]>(loadActivities);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ leads, activities }),
      );
    } catch {
      // Private-mode / quota failures must not break the demo.
    }
  }, [leads, activities]);

  const statusByCode = useCallback(
    (code: string) =>
      STATUSES.find((status) => status.code === code) ?? STATUSES[0],
    [],
  );

  const companyById = useCallback(
    (id: string) => COMPANIES.find((company) => company.id === id),
    [],
  );
  const contactById = useCallback(
    (id: string) => CONTACTS.find((contact) => contact.id === id),
    [],
  );
  const initiativeById = useCallback(
    (id: string) => INITIATIVES.find((initiative) => initiative.id === id),
    [],
  );
  const ownerById = useCallback(
    (id: string) => OWNERS.find((owner) => owner.id === id),
    [],
  );

  const companiesForContact = useCallback((contactId: string) => {
    const contact = CONTACTS.find((c) => c.id === contactId);
    if (!contact) return [];
    return contact.companyIds
      .map((id) => COMPANIES.find((company) => company.id === id))
      .filter((company): company is Company => Boolean(company));
  }, []);

  const findDuplicate = useCallback(
    (contactId: string, initiativeId: string, exceptLeadId?: string) =>
      leads.find(
        (lead) =>
          lead.contactId === contactId &&
          lead.initiativeId === initiativeId &&
          lead.id !== exceptLeadId,
      ),
    [leads],
  );

  const applyStatus = useCallback(
    (lead: Lead, statusCode: string, at: string): Lead => {
      const status = STATUSES.find((s) => s.code === statusCode);
      const closedAt =
        status?.category === "closed" ? (lead.closedAt ?? at) : null;
      return { ...lead, statusCode, closedAt, updatedAt: at };
    },
    [],
  );

  const saveLead = useCallback((lead: Lead) => {
    const at = nowIso();
    const next = applyStatus(lead, lead.statusCode, at);
    setLeads((current) =>
      current.some((item) => item.id === next.id)
        ? current.map((item) => (item.id === next.id ? next : item))
        : [...current, next],
    );
    return next;
  }, [applyStatus]);

  const createLead = useCallback(
    (draft: Omit<Lead, "createdAt" | "updatedAt" | "closedAt">) => {
      const at = nowIso();
      const lead: Lead = {
        ...draft,
        createdAt: at,
        updatedAt: at,
        closedAt: null,
      };
      setLeads((current) => [...current, lead]);
      return lead;
    },
    [],
  );

  const bulkSetStatus = useCallback((ids: string[], statusCode: string) => {
    const at = nowIso();
    setLeads((current) =>
      current.map((lead) =>
        ids.includes(lead.id) ? applyStatus(lead, statusCode, at) : lead,
      ),
    );
  }, [applyStatus]);

  const bulkSetOwner = useCallback((ids: string[], ownerId: string) => {
    const at = nowIso();
    setLeads((current) =>
      current.map((lead) =>
        ids.includes(lead.id)
          ? { ...lead, ownerId, updatedAt: at }
          : lead,
      ),
    );
  }, []);

  const resetDemo = useCallback(() => {
    setLeads(seedLeads());
    setActivities(seedActivities());
  }, []);

  const value = useMemo<CrmContextValue>(
    () => ({
      leads,
      activities,
      statuses: STATUSES,
      owners: OWNERS,
      companies: COMPANIES,
      contacts: CONTACTS,
      initiatives: INITIATIVES,
      currentUserId: CURRENT_USER_ID,
      currentUser: OWNERS[0],
      statusByCode,
      companyById,
      contactById,
      initiativeById,
      ownerById,
      companiesForContact,
      findDuplicate,
      saveLead,
      createLead,
      bulkSetStatus,
      bulkSetOwner,
      resetDemo,
    }),
    [
      leads,
      activities,
      statusByCode,
      companyById,
      contactById,
      initiativeById,
      ownerById,
      companiesForContact,
      findDuplicate,
      saveLead,
      createLead,
      bulkSetStatus,
      bulkSetOwner,
      resetDemo,
    ],
  );

  return <CrmContext.Provider value={value}>{children}</CrmContext.Provider>;
}

export function useCrm(): CrmContextValue {
  const context = useContext(CrmContext);
  if (!context) {
    throw new Error("useCrm must be used inside <CrmProvider>");
  }
  return context;
}
