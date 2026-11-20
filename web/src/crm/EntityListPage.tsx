// P1 master-data lists (E1–E4): Aziende, Contatti, Anagr. Iniziative.
// They exist so the P0 nav is not a set of dead links; they are read-only by design.

import { useCrm } from "./store";
import { formatNumberIt } from "../lib/i18n";

type EntityKind = "aziende" | "contatti" | "iniziative";

const TITLES: Record<EntityKind, { title: string; count: (n: number) => string }> = {
  aziende: { title: "Tutte le aziende", count: (n) => `${formatNumberIt(n)} aziende` },
  contatti: { title: "Tutti i contatti", count: (n) => `${formatNumberIt(n)} contatti` },
  iniziative: { title: "Anagrafiche Iniziative con codici", count: (n) => `${formatNumberIt(n)} iniziative` },
};

export default function EntityListPage({ entity }: { entity: EntityKind }) {
  const crm = useCrm();
  const meta = TITLES[entity];

  const rowCount =
    entity === "aziende"
      ? crm.companies.length
      : entity === "contatti"
        ? crm.contacts.length
        : crm.initiatives.length;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold tracking-tight text-ink">{meta.title}</h1>
          <p className="mt-0.5 text-[12px] text-muted">
            {meta.count(rowCount)} · dati dimostrativi deterministici
          </p>
        </div>
        <span className="rounded-full border border-line bg-surface px-2.5 py-1 text-[10.5px] font-medium text-muted">
          Predefinito
        </span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-line bg-surface shadow-card">
        <table className="w-full border-collapse text-left">
          {entity === "aziende" ? (
            <>
              <thead>
                <tr className="border-b border-line bg-[#F7F7F5] text-[10px] uppercase tracking-[0.08em] text-muted">
                  <th scope="col" className="px-4 py-2.5 font-semibold">Denominazione</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold">Codice Fiscale</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold">Partita IVA</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold">Provincia</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold">1° Macro Settore</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold">Tipologia</th>
                </tr>
              </thead>
              <tbody>
                {crm.companies.map((company) => (
                  <tr key={company.id} className="border-b border-line/70 text-[12.5px] hover:bg-[#FAFAF7]">
                    <td className="px-4 py-2.5 font-medium text-ink">{company.name}</td>
                    <td className="px-4 py-2.5 text-muted tabular-nums">{company.taxCode}</td>
                    <td className="px-4 py-2.5 text-muted tabular-nums">{company.vat}</td>
                    <td className="px-4 py-2.5 text-muted">{company.province}</td>
                    <td className="px-4 py-2.5 text-muted">{company.macroSector}</td>
                    <td className="px-4 py-2.5 text-muted">{company.tipologia}</td>
                  </tr>
                ))}
              </tbody>
            </>
          ) : null}

          {entity === "contatti" ? (
            <>
              <thead>
                <tr className="border-b border-line bg-[#F7F7F5] text-[10px] uppercase tracking-[0.08em] text-muted">
                  <th scope="col" className="px-4 py-2.5 font-semibold">Nome completo</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold">E-mail</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold">Telefono</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold">Maturità anagrafica</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold">Aziende</th>
                </tr>
              </thead>
              <tbody>
                {crm.contacts.map((contact) => (
                  <tr key={contact.id} className="border-b border-line/70 text-[12.5px] hover:bg-[#FAFAF7]">
                    <td className="px-4 py-2.5 font-medium text-ink">{contact.fullName}</td>
                    <td className="px-4 py-2.5 text-muted">{contact.email}</td>
                    <td className="px-4 py-2.5 text-muted tabular-nums">{contact.phone}</td>
                    <td className="px-4 py-2.5 text-muted">{contact.maturity}</td>
                    <td className="px-4 py-2.5 text-muted">
                      {contact.companyIds
                        .map((id) => crm.companyById(id)?.name)
                        .filter(Boolean)
                        .join(" · ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </>
          ) : null}

          {entity === "iniziative" ? (
            <>
              <thead>
                <tr className="border-b border-line bg-[#F7F7F5] text-[10px] uppercase tracking-[0.08em] text-muted">
                  <th scope="col" className="px-4 py-2.5 font-semibold">Codice</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold">Nome</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold">1° Referente</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold">Lead collegati</th>
                </tr>
              </thead>
              <tbody>
                {crm.initiatives.map((initiative) => (
                  <tr key={initiative.id} className="border-b border-line/70 text-[12.5px] hover:bg-[#FAFAF7]">
                    <td className="px-4 py-2.5 font-mono text-[11.5px] text-muted">{initiative.code}</td>
                    <td className="px-4 py-2.5 font-medium text-ink">{initiative.name}</td>
                    <td className="px-4 py-2.5 text-muted">
                      {crm.ownerById(initiative.referenteId)?.name}
                    </td>
                    <td className="px-4 py-2.5 text-muted tabular-nums">
                      {crm.leads.filter((lead) => lead.initiativeId === initiative.id).length}
                    </td>
                  </tr>
                ))}
              </tbody>
            </>
          ) : null}
        </table>
      </div>
    </div>
  );
}
