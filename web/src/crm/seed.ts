// Deterministic Italian seed for the CRM P0 demo.
//
// Every row here is a committed fixture, not a made-up number on screen: the tab
// counts, the grid counts and the footer range are all computed from these arrays.
// The shape mirrors `data/crm_schema.sql` (crm_companies, crm_contacts,
// crm_company_contacts, crm_initiatives, crm_leads, crm_activities) so the UI can be
// pointed at the real API later without changing a single component.

import type {
  Company,
  Contact,
  Initiative,
  Lead,
  LeadActivity,
  LeadStatusDef,
  Owner,
} from "./types";

const pad = (n: number) => String(n).padStart(2, "0");

/** February 2026 is CET (+01:00), so no DST edge case in the fixture window. */
const feb = (day: number, hour: number, minute: number) =>
  `2026-02-${pad(day)}T${pad(hour)}:${pad(minute)}:00+01:00`;

const jan = (day: number, hour: number, minute: number) =>
  `2026-01-${pad(day)}T${pad(hour)}:${pad(minute)}:00+01:00`;

/** The status catalogue is a table, not an enum (spec §4.1, P0 C11). */
export const STATUSES: LeadStatusDef[] = [
  { code: "nuovo", labelIt: "Nuovo", category: "open", order: 10, defaultManual: true, active: true },
  { code: "interessato", labelIt: "Interessato", category: "open", order: 20, defaultAuto: true, active: true },
  { code: "da_contattare", labelIt: "Da contattare", category: "open", order: 30, active: true },
  { code: "in_attesa_di_riscontro", labelIt: "In attesa di riscontro", category: "open", order: 40, active: true },
  { code: "prefattibilita_negativa", labelIt: "Prefattibilità negativa", category: "closed", order: 50, active: true },
  { code: "nessuna_risposta", labelIt: "Nessuna risposta", category: "closed", order: 60, active: true },
  { code: "non_interessato", labelIt: "Non interessato", category: "closed", order: 70, active: true },
  { code: "iscritto_all_evento", labelIt: "Iscritto all'evento", category: "closed", order: 80, active: true },
  { code: "servizio_concluso", labelIt: "Servizio concluso", category: "closed", order: 90, active: true },
  { code: "contratto_concluso", labelIt: "Contratto concluso", category: "closed", order: 100, active: true },
  { code: "interessato_inbuyer", labelIt: "Interessato InBuyer", category: "open", order: 110, legacy: true, active: true },
  { code: "concluso", labelIt: "Concluso", category: "closed", order: 120, legacy: true, active: true },
  { code: "da_richiamare", labelIt: "Da richiamare", category: "open", order: 130, legacy: true, active: true },
  { code: "perso", labelIt: "Perso", category: "closed", order: 140, legacy: true, active: true },
];

export const OWNERS: Owner[] = [
  { id: "marta", name: "Marta Rossi", initials: "MR", role: "Sales" },
  { id: "luca", name: "Luca Bianchi", initials: "LB", role: "Sales" },
  { id: "elena", name: "Elena Fabbri", initials: "EF", role: "Sales" },
];

export const CURRENT_USER_ID = "marta";

export const COMPANIES: Company[] = [
  { id: "c1", name: "Moltren Società Agricola Semplice", macroSector: "Agroalimentare", sector: "Agricole e Vivaistiche", province: "RAVENNA", tipologia: "PMI", taxCode: "01234567890", vat: "IT01234567890" },
  { id: "c2", name: "Officine Meccaniche Ferrari", macroSector: "Meccanica", sector: "Meccanica di precisione", province: "BOLOGNA", tipologia: "Media impresa", taxCode: "02345678901", vat: "IT02345678901" },
  { id: "c3", name: "Lanificio Fratelli Colombo", macroSector: "Moda e Tessile", sector: "Tessile", province: "PRATO", tipologia: "PMI", taxCode: "03456789012", vat: "IT03456789012" },
  { id: "c4", name: "Studio Luce & Arredo", macroSector: "Arredo e Design", sector: "Illuminazione", province: "MILANO", tipologia: "Micro impresa", taxCode: "04567890123", vat: "IT04567890123" },
  { id: "c5", name: "TechSolutions Consulting", macroSector: "ICT e Digitale", sector: "Software", province: "TORINO", tipologia: "PMI", taxCode: "05678901234", vat: "IT05678901234" },
  { id: "c6", name: "Pastificio Artigianale Esposito", macroSector: "Food & Beverage", sector: "Pasta", province: "NAPOLI", tipologia: "Micro impresa", taxCode: "06789012345", vat: "IT06789012345" },
  { id: "c7", name: "NovaBio Pharma", macroSector: "Biotech & Farmaceutica", sector: "Farmaceutica", province: "ROMA", tipologia: "Grande impresa", taxCode: "07890123456", vat: "IT07890123456" },
  { id: "c8", name: "Ceramiche Emiliane", macroSector: "Edilizia e Materiali", sector: "Ceramica", province: "MODENA", tipologia: "PMI", taxCode: "08901234567", vat: "IT08901234567" },
  { id: "c9", name: "Robotics Dynamics", macroSector: "Meccanica", sector: "Automazione", province: "VICENZA", tipologia: "Media impresa", taxCode: "09012345678", vat: "IT09012345678" },
  { id: "c10", name: "Vigneti & Cantina Fontana", macroSector: "Agroalimentare", sector: "Vitivinicolo", province: "VERONA", tipologia: "PMI", taxCode: "00123456789", vat: "IT00123456789" },
  { id: "c11", name: "Pelletteria Toscana Bianchi", macroSector: "Moda e Tessile", sector: "Pelletteria", province: "FIRENZE", tipologia: "PMI", taxCode: "00234567890", vat: "IT00234567890" },
  { id: "c12", name: "Idrotermica Lombarda", macroSector: "Edilizia e Materiali", sector: "Termoidraulica", province: "BERGAMO", tipologia: "Micro impresa", taxCode: "00345678901", vat: "IT00345678901" },
];

export const CONTACTS: Contact[] = [
  { id: "p1", fullName: "Giuseppe Molinari", email: "g.molinari@moltrenagricola.it", phone: "+39 0544 892110", companyIds: ["c1"], maturity: "Prospect", privacyConsent: true },
  { id: "p2", fullName: "Ing. Laura Ricci", email: "l.ricci@omferrari.it", phone: "+39 051 445 7812", companyIds: ["c2"], maturity: "Lead", privacyConsent: true },
  { id: "p3", fullName: "Marco Brambilla", email: "m.brambilla@lanificiocolombo.it", phone: "+39 0574 331 208", companyIds: ["c3"], maturity: "Cliente", privacyConsent: true },
  { id: "p4", fullName: "Elena Moretti", email: "e.moretti@studiolucearredo.it", phone: "+39 02 8725 4410", companyIds: ["c4"], maturity: "Prospect", privacyConsent: false },
  { id: "p5", fullName: "Davide Ferri", email: "d.ferri@techsolutions.it", phone: "+39 011 663 9021", companyIds: ["c5"], maturity: "Lead", privacyConsent: true },
  { id: "p6", fullName: "Chiara Esposito", email: "c.esposito@pastificioesposito.it", phone: "+39 081 552 7781", companyIds: ["c6"], maturity: "Prospect", privacyConsent: true },
  { id: "p7", fullName: "Dott. Roberto Bianchi", email: "r.bianchi@novabio.it", phone: "+39 06 4991 2270", companyIds: ["c7"], maturity: "Cliente", privacyConsent: true },
  { id: "p8", fullName: "Silvia Marchetti", email: "s.marchetti@ceramicheemiliane.it", phone: "+39 059 374 118", companyIds: ["c8"], maturity: "Lead", privacyConsent: true },
  { id: "p9", fullName: "Andrea Colombo", email: "a.colombo@roboticsdynamics.it", phone: "+39 0444 289 330", companyIds: ["c9"], maturity: "Prospect", privacyConsent: true },
  { id: "p10", fullName: "Giulia Fontana", email: "g.fontana@vignetifontana.it", phone: "+39 045 812 5566", companyIds: ["c10", "c11"], maturity: "Lead", privacyConsent: true },
  { id: "p11", fullName: "Paolo Greco", email: "p.greco@omferrari.it", phone: "+39 051 445 7815", companyIds: ["c2"], maturity: "Lead", privacyConsent: true },
  { id: "p12", fullName: "Francesca Rizzo", email: "f.rizzo@techsolutions.it", phone: "+39 011 663 9024", companyIds: ["c5"], maturity: "Prospect", privacyConsent: false },
  { id: "p13", fullName: "Matteo Villa", email: "m.villa@ceramicheemiliane.it", phone: "+39 059 374 121", companyIds: ["c8"], maturity: "Prospect", privacyConsent: true },
  { id: "p14", fullName: "Anna De Luca", email: "a.deluca@studiolucearredo.it", phone: "+39 02 8725 4418", companyIds: ["c4"], maturity: "Prospect", privacyConsent: true },
];

export const INITIATIVES: Initiative[] = [
  { id: "i1", code: "INI-2025-000101", name: "Missione Svezia - Wine", referenteId: "marta" },
  { id: "i2", code: "INI-2025-000102", name: "Missione Industriale Hannover Messe", referenteId: "luca" },
  { id: "i3", code: "INI-2025-000103", name: "Progetto Export Moda 2025", referenteId: "marta" },
  { id: "i4", code: "INI-2025-000104", name: "Incoming Designers", referenteId: "elena" },
  { id: "i5", code: "INI-2025-000105", name: "Bando Digital Export", referenteId: "luca" },
  { id: "i6", code: "INI-2025-000106", name: "Foodex Japan Edition", referenteId: "elena" },
  { id: "i7", code: "INI-2025-000107", name: "Cluster Life Science", referenteId: "marta" },
  { id: "i8", code: "INI-2025-000108", name: "Tavolo Edilizia Sostenibile", referenteId: "luca" },
];

/**
 * Initiatives a company can plausibly join, most specific first. A company is promoted
 * through three of these (and a fourth for the closed history), which keeps every
 * (Contatto, Iniziativa) pair unique without inventing cross-sector matches.
 */
const COMPANY_INITIATIVES: Record<string, string[]> = {
  c1: ["i6", "i1", "i5", "i2"], // agroalimentare: Foodex, Wine, Digital Export, Hannover
  c2: ["i2", "i5", "i7", "i8"], // meccanica: Hannover, Digital Export, Life Science, Edilizia
  c3: ["i3", "i4", "i5", "i1"], // moda: Export Moda, Designers, Digital Export, Wine
  c4: ["i4", "i3", "i5", "i2"], // arredo: Designers, Export Moda, Digital Export, Hannover
  c5: ["i5", "i2", "i4", "i7"], // ICT: Digital Export, Hannover, Designers, Life Science
  c6: ["i6", "i1", "i5", "i3"], // food: Foodex, Wine, Digital Export, Export Moda
  c7: ["i7", "i5", "i2", "i8"], // pharma: Life Science, Digital Export, Hannover, Edilizia
  c8: ["i8", "i2", "i5", "i7"], // edilizia: Edilizia, Hannover, Digital Export, Life Science
  c9: ["i2", "i5", "i7", "i3"], // meccanica: Hannover, Digital Export, Life Science, Export Moda
  c10: ["i1", "i6", "i5", "i2"], // vino: Wine, Foodex, Digital Export, Hannover
  c11: ["i3", "i4", "i5", "i1"], // pelletteria: Export Moda, Designers, Digital Export, Wine
  c12: ["i8", "i2", "i5", "i4"], // termoidraulica: Edilizia, Hannover, Digital Export, Designers
};

const TITLES = [
  "Interesse partecipazione B2B agroalimentare Stoccolma",
  "Richiesta stand collettivo fiera Hannover Messe",
  "Consulenza doganale e certificazioni export",
  "Adesione workshop contrattualistica internazionale",
  "Voucher digital export bando regionale",
  "Supporto etichettatura FDA e partecipazione Foodex",
  "Accreditamento clinico dispositivi medici",
  "Consulenza per protocollo LEED e fornitura",
  "Progetto automazione industriale e linee robotizzate",
  "Richiesta inserimento catalogo vini biologici",
  "Missione incoming buyer delegazione tedesca",
  "Partecipazione collettiva Salone del Mobile",
  "Servizio di traduzione contrattualistica",
  "Analisi di mercato per espansione estero",
];

const SOURCES = ["Manifestazione di interesse", "Evento", "Contatto diretto", "Referral"];
const TIPI_INTERESSE = ["Prima Assistenza", "Approfondimento", "Partecipazione", "Richiesta offerta"];

const OPEN_PLAN: string[] = [
  ...Array.from({ length: 18 }, () => "interessato"),
  ...Array.from({ length: 11 }, () => "da_contattare"),
  ...Array.from({ length: 13 }, () => "in_attesa_di_riscontro"),
];

const CLOSED_PLAN: Array<{ code: string; ownerId: string }> = [
  { code: "servizio_concluso", ownerId: "marta" },
  { code: "contratto_concluso", ownerId: "marta" },
  { code: "iscritto_all_evento", ownerId: "marta" },
  { code: "non_interessato", ownerId: "luca" },
  { code: "perso", ownerId: "elena" },
  { code: "nessuna_risposta", ownerId: "luca" },
];

const pairKey = (contactId: string, initiativeId: string) =>
  `${contactId}|${initiativeId}`;

function initiativesFor(companyId: string): Initiative[] {
  return COMPANY_INITIATIVES[companyId]
    .map((id) => INITIATIVES.find((initiative) => initiative.id === id))
    .filter((initiative): initiative is Initiative => Boolean(initiative));
}

/**
 * The demo world must satisfy the same rule the UI enforces: at most one lead per
 * (Contatto, Anagrafica interesse). We build candidates in a deterministic order and
 * skip any pair already used, so the uniqueness warning only fires for a real attempt.
 */
function buildLeads(): Lead[] {
  const used = new Set<string>();
  const leads: Lead[] = [];
  let cursor = 0;

  while (leads.length < OPEN_PLAN.length && cursor < 400) {
    const contact = CONTACTS[cursor % CONTACTS.length];
    const companyId = contact.companyIds[cursor % contact.companyIds.length];
    const round = Math.floor(cursor / CONTACTS.length);
    const options = initiativesFor(companyId);
    const initiative = options[round % options.length];
    cursor += 1;
    const key = pairKey(contact.id, initiative.id);
    if (used.has(key)) continue;
    used.add(key);

    const index = leads.length;
    const company = COMPANIES.find((entry) => entry.id === companyId)!;
    const day = 14 + (index % 9);
    const hour = 9 + (index % 8);
    const minute = (index * 7) % 60;
    const createdAt = feb(day, hour, minute);
    const updatedAt = feb(day, Math.min(18, hour + 2), (minute + 25) % 60);
    leads.push({
      id: `L-${9020 + index}`,
      argomento: `${TITLES[index % TITLES.length]} — ${company.name}`,
      descrizione:
        "Nuovo lead generato dal portale Web Promos Italia. Form di candidatura compilato correttamente dal contatto per conto dell'azienda.",
      requests:
        "Vorrei essere contattato per ricevere informazioni dettagliate sulla missione e capire le modalità di partecipazione.",
      noteMigrate: "",
      contactId: contact.id,
      companyId,
      initiativeId: initiative.id,
      statusCode: OPEN_PLAN[index],
      ownerId: "marta",
      source: SOURCES[index % SOURCES.length],
      tipoInteresse: TIPI_INTERESSE[index % TIPI_INTERESSE.length],
      manifestazioneOrigine: `MI-2025-0${8420 + index}`,
      createdAt,
      updatedAt,
      closedAt: null,
    });
  }

  let closedCursor = 5;
  let closedIndex = 0;
  while (closedIndex < CLOSED_PLAN.length && closedCursor < 400) {
    const contact = CONTACTS[closedCursor % CONTACTS.length];
    const companyId = contact.companyIds[0];
    const options = initiativesFor(companyId);
    const initiative = options[options.length - 1];
    closedCursor += 1;
    const key = pairKey(contact.id, initiative.id);
    if (used.has(key)) continue;
    used.add(key);

    const plan = CLOSED_PLAN[closedIndex];
    const company = COMPANIES.find((entry) => entry.id === companyId)!;
    const createdAt = jan(8 + closedIndex, 10, (closedIndex * 11) % 60);
    const closedAt = jan(20 + closedIndex, 16, (closedIndex * 13) % 60);
    leads.push({
      id: `L-${9070 + closedIndex}`,
      argomento: `${TITLES[(closedIndex + 6) % TITLES.length]} — ${company.name}`,
      descrizione: "Lead chiuso nel ciclo precedente; conservato per le viste storiche.",
      requests: "Richiesta di informazioni gestita e archiviata.",
      noteMigrate: "Migrato dal CRM precedente.",
      contactId: contact.id,
      companyId,
      initiativeId: initiative.id,
      statusCode: plan.code,
      ownerId: plan.ownerId,
      source: SOURCES[(closedIndex + 2) % SOURCES.length],
      tipoInteresse: TIPI_INTERESSE[(closedIndex + 1) % TIPI_INTERESSE.length],
      manifestazioneOrigine: `MI-2025-0${8320 + closedIndex}`,
      createdAt,
      updatedAt: closedAt,
      closedAt,
    });
    closedIndex += 1;
  }

  return leads;
}

export const LEADS: Lead[] = buildLeads();

export const ACTIVITIES: LeadActivity[] = [
  {
    id: "a1",
    leadId: "L-9020",
    kind: "email",
    title: "E-mail inviata da Marta Rossi",
    body: "Foodex Japan: informazioni e prossimi passi. CRM:0085001",
    at: feb(20, 10, 45),
    authorId: "marta",
  },
  {
    id: "a2",
    leadId: "L-9020",
    kind: "call",
    title: "Telefonata da Marta Rossi",
    body: "Primo contatto. Il referente conferma la piena disponibilità per gli incontri B2B del 28 Marzo.",
    at: feb(21, 15, 30),
    authorId: "marta",
  },
  {
    id: "a3",
    leadId: "L-9020",
    kind: "note",
    title: "Nota inserita da Marta Rossi",
    body: "Azienda interessata, verificare incentivi camerali prima di confermare il preventivo finale.",
    at: feb(22, 16, 15),
    authorId: "marta",
  },
];
