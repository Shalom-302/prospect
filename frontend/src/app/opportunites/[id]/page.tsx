"use client";

import Link from "next/link";
import { use, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { ArrowLeft, Building2, Download, ExternalLink, Gauge, Send, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, fetcher, fmtDate, KIND_LABELS, Opportunity, PROFILE_LABELS } from "@/lib/api";
import { PageHeader, ScoreBreakdown, Spin, StatusSelect, useAction } from "@/components/shared";
import { GeneratorPanel } from "@/components/generator-panel";
import { ActivityLog } from "@/components/activity-log";

export default function OpportunityPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data: o, mutate } = useSWR<Opportunity>(`/api/opportunities/${id}`, fetcher);
  const { busy, run } = useAction();
  const [notes, setNotes] = useState<string | null>(null);
  const [nextAction, setNextAction] = useState<{ text: string; date: string } | null>(null);

  if (!o) return <p className="text-sm text-muted-foreground">Chargement…</p>;

  const patch = (json: object, msg?: string) => run("patch", () => api(`/api/opportunities/${id}`, { method: "PATCH", json }), msg).then(() => mutate());
  const back = o.kind === "job" ? "/offres" : o.kind === "freelance" ? "/freelance" : "/b2b";

  async function prepare() {
    const a = await run("prep", () => api("/api/applications", { method: "POST", json: { opportunity_id: o!.id, language: o!.language || "fr" } }));
    if (a) router.push(`/candidatures/${a.id}`);
  }

  async function linkCompany() {
    const website = prompt(`Site web de « ${o!.company_name} » (facultatif, pour rechercher les contacts publics) :`) ?? null;
    if (website === null) return;
    const r = await run("company", () => api("/api/companies", { method: "POST", json: { name: o!.company_name || "Entreprise", website: website || null, country: "", scan: !!website } }));
    if (r) {
      await patch({ company_id: r.company.id }, r.created ? "Fiche entreprise créée et liée" : "Entreprise existante liée");
    }
  }

  return (
    <div className="mx-auto max-w-7xl">
      <Link href={back} className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"><ArrowLeft className="size-3.5" /> Retour</Link>
      <PageHeader title={o.title} subtitle={[o.company_name || "Entreprise non précisée", o.location, o.remote ? "Remote" : null, KIND_LABELS[o.kind]].filter(Boolean).join(" · ")}>
        <StatusSelect value={o.status} onChange={(s) => patch({ status: s }, "Statut mis à jour")} />
        {o.apply_url && <Button asChild variant="outline"><a href={o.apply_url} target="_blank" rel="noreferrer"><ExternalLink className="size-4" /> Postuler sur le site</a></Button>}
        <Button onClick={prepare} disabled={busy === "prep"}><Spin on={busy === "prep"} /><Send className="size-4" /> Préparer la candidature</Button>
      </PageHeader>

      {o.needs_verification && (
        <div className="mb-6 flex flex-col gap-3 rounded-lg border border-dashed bg-background p-4 text-sm sm:flex-row sm:items-center">
          <p className="flex-1">Résultat de recherche web : ce n&apos;est pas encore une annonce confirmée. Récupérez la page source pour vérifier qu&apos;elle est réelle, ouverte et complète.</p>
          <Button variant="outline" onClick={() => run("fetch", () => api(`/api/opportunities/${id}/fetch`, { method: "POST" }), "Annonce complète récupérée").then(() => mutate())} disabled={busy === "fetch"}>
            <Spin on={busy === "fetch"} /><Download className="size-4" /> Récupérer l&apos;annonce complète
          </Button>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="text-base">Annonce</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                <Info label="Contrat">{o.contract_type || "—"}</Info>
                <Info label="Rémunération">{o.salary ? `${o.salary} ${o.currency}` : "—"}</Info>
                <Info label="Télétravail">{o.remote == null ? "—" : o.remote ? "Oui" : "Non"}</Info>
                <Info label="Publiée">{fmtDate(o.published_at)}</Info>
                <Info label="Date limite">{fmtDate(o.deadline)}</Info>
                <Info label="Langue">{o.language?.toUpperCase() || "—"}</Info>
                <Info label="Source">{o.source_url ? <a className="underline" href={o.source_url} target="_blank" rel="noreferrer">{o.source}</a> : o.source}</Info>
                <Info label="Collectée">{fmtDate(o.collected_at)}</Info>
                <Info label="Dernière vérification">{fmtDate(o.last_checked_at)}</Info>
              </dl>
              {!!o.skills?.length && <div className="flex flex-wrap gap-1">{o.skills.map((s) => <span key={s} className="rounded bg-muted px-1.5 py-0.5 text-xs">{s}</span>)}</div>}
              <div className="max-h-[480px] overflow-y-auto whitespace-pre-wrap rounded-md bg-muted/40 p-3 text-sm leading-relaxed">{o.description || "Pas de description."}</div>
            </CardContent>
          </Card>
          <GeneratorPanel opportunityId={o.id} defaultProfile={o.profile_key === "kortex" ? "kortex" : "shalom"} defaultLanguage={o.language || "fr"}
            types={o.kind === "b2b" ? ["b2b_proposal", "email"] : ["cover_letter", "email"]} onChange={() => mutate()} />
          <ActivityLog activities={o.activities || []} opportunityId={o.id} companyId={o.company_id} onChange={() => mutate()} />
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base"><Gauge className="size-4" /> Qualification</CardTitle>
              <Button size="sm" variant="outline" disabled={busy === "q"} onClick={() => run("q", () => api(`/api/opportunities/${id}/qualify`, { method: "POST" }), "Qualification mise à jour").then(() => mutate())}>
                <Spin on={busy === "q"} /> Analyser (IA)
              </Button>
            </CardHeader>
            <CardContent><ScoreBreakdown analysis={o.analysis} /></CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Suivi</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div>Profil : <b>{PROFILE_LABELS[o.profile_key]}</b>{" "}
                <button className="text-xs underline text-muted-foreground" onClick={() => patch({ profile_key: o.profile_key === "shalom" ? "kortex" : "shalom" })}>changer</button>
              </div>
              <div className="flex items-center gap-2">
                <Building2 className="size-4" />
                {o.company_id ? <Link className="underline" href={`/entreprises/${o.company_id}`}>Fiche entreprise</Link>
                  : <button className="underline" onClick={linkCompany}>Créer / lier la fiche entreprise</button>}
              </div>
              <div className="space-y-1.5">
                <div className="text-xs text-muted-foreground">Prochaine action</div>
                <Input value={nextAction?.text ?? o.next_action} onChange={(e) => setNextAction({ text: e.target.value, date: nextAction?.date ?? o.next_action_date?.slice(0, 10) ?? "" })} placeholder="ex. Relancer la DRH" />
                <Input type="date" value={nextAction?.date ?? o.next_action_date?.slice(0, 10) ?? ""} onChange={(e) => setNextAction({ text: nextAction?.text ?? o.next_action, date: e.target.value })} />
                {nextAction && <Button size="sm" onClick={() => patch({ next_action: nextAction.text, next_action_date: nextAction.date ? new Date(nextAction.date).toISOString() : null }, "Enregistré").then(() => setNextAction(null))}>Enregistrer</Button>}
              </div>
              <div className="space-y-1.5">
                <div className="text-xs text-muted-foreground">Notes</div>
                <Textarea rows={4} value={notes ?? o.notes ?? ""} onChange={(e) => setNotes(e.target.value)} />
                {notes !== null && <Button size="sm" onClick={() => patch({ notes }, "Notes enregistrées").then(() => setNotes(null))}>Enregistrer</Button>}
              </div>
              <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={() => confirm("Supprimer cette opportunité ?") && run("del", () => api(`/api/opportunities/${id}`, { method: "DELETE" })).then(() => router.push(back))}>
                <Trash2 className="size-3.5" /> Supprimer
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Info({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><dt className="text-xs text-muted-foreground">{label}</dt><dd className="truncate">{children}</dd></div>;
}
