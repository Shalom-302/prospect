"use client";

import Link from "next/link";
import { use, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { ArrowLeft, ExternalLink, Gauge, Plus, Radar, Send, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, Company, CONFIDENCE_LABELS, CONTACT_LABELS, fetcher, fmtDate } from "@/lib/api";
import { ConfidenceBadge, PageHeader, ScoreBadge, ScoreBreakdown, Spin, StatusBadge, StatusSelect, useAction } from "@/components/shared";
import { GeneratorPanel } from "@/components/generator-panel";
import { ActivityLog } from "@/components/activity-log";

const KIND_LABEL: Record<string, string> = { email: "Email", phone: "Téléphone", contact_form: "Formulaire de contact", careers_page: "Page carrières", linkedin: "LinkedIn" };

export default function CompanyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data: c, mutate } = useSWR<Company>(`/api/companies/${id}`, fetcher);
  const { busy, run } = useAction();
  const [edit, setEdit] = useState<Partial<Company> | null>(null);
  const [sites, setSites] = useState<any[] | null>(null);

  if (!c) return <p className="text-sm text-muted-foreground">Chargement…</p>;
  const patch = (json: object, msg?: string) => run("patch", () => api(`/api/companies/${id}`, { method: "PATCH", json }), msg).then(() => mutate());

  async function scan() {
    const r = await run("scan", () => api(`/api/companies/${id}/scan`, { method: "POST" }));
    if (r) {
      r.ok ? toast.success(`${r.pages_visited.length} page(s) lue(s), ${r.contacts_added} nouveau(x) contact(s)`) : toast.error(r.message || "Site inaccessible");
      if (r.blocked?.length) toast.message(r.blocked.slice(0, 3).join(" ; "));
      mutate();
    }
  }

  async function prepare() {
    const a = await run("prep", () => api("/api/applications", { method: "POST", json: { company_id: c!.id, profile_key: "kortex" } }));
    if (a) router.push(`/candidatures/${a.id}`);
  }

  async function findSite() {
    const r = await run("find", () => api(`/api/companies/${id}/find-website`, { method: "POST" }));
    if (r) { setSites(r); if (!r.length) toast.message("Aucun site candidat trouvé : renseignez-le manuellement."); }
  }

  async function chooseSite(url: string) {
    await patch({ website: url }, "Site enregistré");
    setSites(null);
    await scan();
  }

  const e = edit || {};
  return (
    <div className="mx-auto max-w-7xl">
      <Link href="/entreprises" className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"><ArrowLeft className="size-3.5" /> Entreprises</Link>
      <PageHeader title={c.name} subtitle={[c.sector, c.city, c.country].filter(Boolean).join(" · ")}>
        <StatusSelect value={c.status} onChange={(s) => patch({ status: s }, "Statut mis à jour")} />
        {c.website && <Button variant="outline" asChild><a href={c.website} target="_blank" rel="noreferrer"><ExternalLink className="size-4" /> Site</a></Button>}
        {c.website ? (
          <Button variant="outline" onClick={scan} disabled={busy === "scan"}><Spin on={busy === "scan"} /><Radar className="size-4" /> Scanner le site</Button>
        ) : (
          <Button variant="outline" onClick={findSite} disabled={busy === "find"}><Spin on={busy === "find"} /><Radar className="size-4" /> Trouver le site officiel</Button>
        )}
        <Button onClick={prepare} disabled={busy === "prep"}><Spin on={busy === "prep"} /><Send className="size-4" /> Préparer une démarche</Button>
      </PageHeader>

      {sites && !!sites.length && (
        <Card className="mb-6">
          <CardHeader className="flex items-center justify-between">
            <CardTitle className="text-base">Sites candidats — choisissez le site officiel</CardTitle>
            <Button size="sm" variant="ghost" onClick={() => setSites(null)}>Fermer</Button>
          </CardHeader>
          <CardContent>
            <ul className="divide-y">
              {sites.map((s) => (
                <li key={s.domain} className="flex items-center gap-3 py-2 text-sm">
                  <div className="min-w-0 flex-1">
                    <a className="font-medium hover:underline" href={s.url} target="_blank" rel="noreferrer">{s.domain}</a>
                    <div className="truncate text-xs text-muted-foreground">{s.title} — {s.snippet}</div>
                  </div>
                  <Button size="sm" onClick={() => chooseSite(s.url)}>C&apos;est celui-ci</Button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-6">
          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle className="text-base">Identité et informations</CardTitle>
              {!edit ? <Button size="sm" variant="ghost" onClick={() => setEdit({})}>Modifier</Button>
                : <div className="flex gap-2"><Button size="sm" variant="ghost" onClick={() => setEdit(null)}>Annuler</Button><Button size="sm" onClick={() => patch(edit, "Enregistré").then(() => setEdit(null))}>Enregistrer</Button></div>}
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {edit ? (
                <div className="grid gap-2 sm:grid-cols-2">
                  {(["name", "website", "sector", "country", "city", "address"] as const).map((k) => (
                    <Input key={k} placeholder={k} defaultValue={(c as any)[k] || ""} onChange={(ev) => setEdit({ ...e, [k]: ev.target.value })} />
                  ))}
                  <Textarea className="sm:col-span-2" rows={5} defaultValue={c.description} onChange={(ev) => setEdit({ ...e, description: ev.target.value })} />
                </div>
              ) : (
                <>
                  <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                    <Info label="Site">{c.website ? <a className="underline" href={c.website} target="_blank" rel="noreferrer">{c.domain}</a> : "—"}</Info>
                    <Info label="Adresse">{c.address || "—"}</Info>
                    <Info label="Source">{c.source_url ? <a className="underline" href={c.source_url} target="_blank" rel="noreferrer">{c.source_name}</a> : c.source_name}</Info>
                    <Info label="Collectée">{fmtDate(c.collected_at)}</Info>
                    <Info label="Site vérifié le">{fmtDate(c.verified_at)}</Info>
                  </dl>
                  <p className="whitespace-pre-wrap text-muted-foreground">{c.description || "Pas de description."}</p>
                </>
              )}
            </CardContent>
          </Card>

          <ContactsCard company={c} onChange={() => mutate()} />

          {!!c.opportunities?.length && (
            <Card>
              <CardHeader><CardTitle className="text-base">Opportunités identifiées</CardTitle></CardHeader>
              <CardContent className="space-y-1">
                {c.opportunities.map((o) => (
                  <Link key={o.id} href={`/opportunites/${o.id}`} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted">
                    <ScoreBadge score={o.score} method={o.score_method} /><span className="flex-1 truncate">{o.title}</span><StatusBadge status={o.status} />
                  </Link>
                ))}
              </CardContent>
            </Card>
          )}

          <GeneratorPanel companyId={c.id} defaultProfile="kortex" types={["b2b_proposal", "email", "cover_letter"]} onChange={() => mutate()} />
          <ActivityLog activities={c.activities || []} companyId={c.id} onChange={() => mutate()} />
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base"><Gauge className="size-4" /> Pertinence</CardTitle>
              <Button size="sm" variant="outline" disabled={busy === "q"} onClick={() => run("q", () => api(`/api/companies/${id}/qualify`, { method: "POST" }), "Qualification mise à jour").then(() => mutate())}>
                <Spin on={busy === "q"} /> Analyser (IA)
              </Button>
            </CardHeader>
            <CardContent><ScoreBreakdown analysis={c.analysis} /></CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">Rendez-vous et prochaines actions</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              <NextAction company={c} onSave={(json) => patch(json, "Enregistré")} />
              <Textarea rows={4} placeholder="Notes" defaultValue={c.notes} onBlur={(ev) => ev.target.value !== c.notes && patch({ notes: ev.target.value }, "Notes enregistrées")} />
              <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={() => confirm("Supprimer cette entreprise et ses contacts ?") && run("del", () => api(`/api/companies/${id}`, { method: "DELETE" })).then(() => router.push("/entreprises"))}>
                <Trash2 className="size-3.5" /> Supprimer
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function NextAction({ company, onSave }: { company: Company; onSave: (j: object) => void }) {
  const [text, setText] = useState(company.next_action);
  const [date, setDate] = useState(company.next_action_date?.slice(0, 10) || "");
  return (
    <div className="space-y-2">
      <Input placeholder="ex. Appeler la DSI, RDV le…" value={text} onChange={(e) => setText(e.target.value)} />
      <div className="flex gap-2">
        <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        <Button size="sm" onClick={() => onSave({ next_action: text, next_action_date: date ? new Date(date).toISOString() : null })}>OK</Button>
      </div>
    </div>
  );
}

function ContactsCard({ company, onChange }: { company: Company; onChange: () => void }) {
  const [adding, setAdding] = useState(false);
  const [f, setF] = useState({ kind: "email", value: "", label: "general", person_name: "", confidence: "found_unverified", source_url: "" });
  const { run } = useAction();
  async function add() {
    const r = await run("add", () => api(`/api/companies/${company.id}/contacts`, { method: "POST", json: f }), "Contact ajouté");
    if (r) { setAdding(false); setF({ ...f, value: "", person_name: "", source_url: "" }); onChange(); }
  }
  const contacts = company.contacts || [];
  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle className="text-base">Coordonnées professionnelles</CardTitle>
        <Button size="sm" variant="ghost" onClick={() => setAdding(!adding)}><Plus className="size-3.5" /> Ajouter</Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {adding && (
          <div className="grid gap-2 rounded-md border p-3 sm:grid-cols-2">
            <Select value={f.kind} onValueChange={(v) => setF({ ...f, kind: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{Object.entries(KIND_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
            </Select>
            <Input placeholder="Valeur" value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} />
            <Select value={f.label} onValueChange={(v) => setF({ ...f, label: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{Object.entries(CONTACT_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
            </Select>
            <Select value={f.confidence} onValueChange={(v) => setF({ ...f, confidence: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{Object.entries(CONFIDENCE_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
            </Select>
            <Input placeholder="Nom de la personne (facultatif)" value={f.person_name} onChange={(e) => setF({ ...f, person_name: e.target.value })} />
            <Input placeholder="URL source (obligatoire si vérifié)" value={f.source_url} onChange={(e) => setF({ ...f, source_url: e.target.value })} />
            <Button className="sm:col-span-2" onClick={add} disabled={!f.value}>Enregistrer</Button>
          </div>
        )}
        {!contacts.length && <p className="text-sm text-muted-foreground">Aucun contact. Scannez le site officiel ou ajoutez un contact trouvé (avec sa source).</p>}
        <ul className="divide-y">
          {contacts.map((ct) => (
            <li key={ct.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
              <span className="w-28 shrink-0 text-xs text-muted-foreground">{KIND_LABEL[ct.kind] || ct.kind}</span>
              <span className="min-w-0 flex-1 truncate font-medium">
                {ct.kind === "email" ? <a href={`mailto:${ct.value}`}>{ct.value}</a> : ct.value.startsWith("http") ? <a className="hover:underline" href={ct.value} target="_blank" rel="noreferrer">{ct.value}</a> : ct.value}
                {ct.person_name && <span className="font-normal text-muted-foreground"> · {ct.person_name}</span>}
              </span>
              <span className="text-xs text-muted-foreground">{CONTACT_LABELS[ct.label] || ct.label}</span>
              <ConfidenceBadge confidence={ct.confidence} />
              {ct.source_url && <a href={ct.source_url} target="_blank" rel="noreferrer" className="text-[11px] text-muted-foreground underline">source · {fmtDate(ct.found_at)}</a>}
              <button className="text-muted-foreground hover:text-foreground" onClick={() => confirm("Supprimer ce contact ?") && run("d", () => api(`/api/contacts/${ct.id}`, { method: "DELETE" })).then(onChange)}><Trash2 className="size-3.5" /></button>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function Info({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><dt className="text-xs text-muted-foreground">{label}</dt><dd className="truncate">{children}</dd></div>;
}
