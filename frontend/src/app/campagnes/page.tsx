"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { Megaphone } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, Company, fetcher, fmtDate, PROFILE_LABELS } from "@/lib/api";
import { Empty, PageHeader, ScoreBadge, Spin, StatusBadge, useAction } from "@/components/shared";

const CAMPAIGN_STATUS: Record<string, string> = {
  generating: "Rédaction en cours",
  review: "À relire et valider",
  sending: "Envoi en cours",
  paused: "En pause",
  done: "Terminé",
};

export default function CampaignsPage() {
  const router = useRouter();
  const { data: campaigns } = useSWR<any[]>("/api/campaigns", fetcher, { refreshInterval: 10000 });
  const { data: status } = useSWR<any>("/api/outreach/status", fetcher);
  const [f, setF] = useState({ q: "", sector: "", city: "" });
  const qs = useMemo(() => new URLSearchParams({ has_email: "true", limit: "300", ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)) }).toString(), [f]);
  const { data: companies } = useSWR<{ items: Company[] }>(`/api/companies?${qs}`, fetcher);
  const [selected, setSelected] = useState<number[]>([]);
  const [form, setForm] = useState({ name: "", profile_key: "kortex", language: "fr", instructions: "" });
  const { busy, run } = useAction();

  const toggle = (id: number, v: boolean) => setSelected(v ? [...selected, id] : selected.filter((x) => x !== id));
  async function create() {
    const r = await run("create", () => api("/api/campaigns", { method: "POST", json: { ...form, name: form.name || `Lot du ${new Date().toLocaleDateString("fr-FR")}`, company_ids: selected } }),
      "Lot créé : l'IA rédige un email personnalisé par entreprise");
    if (r) router.push(`/campagnes/${r.id}`);
  }

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title="Campagnes (envoi par lots)" subtitle="Sélectionnez des prospects, l'IA rédige un email personnalisé pour chacun, vous relisez et validez le lot une fois : l'envoi est ensuite étalé pour préserver la délivrabilité." />
      {status && (
        <div className="mb-6 grid gap-3 sm:grid-cols-4">
          <Stat label="Envoyés aujourd'hui" value={`${status.sent_today} / ${status.daily_limit}`} hint={status.phase} />
          <Stat label="Fenêtre d'envoi" value={status.in_window ? "Ouverte" : "Fermée"} hint={`${status.hours} h, lun.–ven. (Abidjan)`} />
          <Stat label="Taux de réponse" value={`${status.reply_rate} %`} hint={`${status.replied} réponse(s) / ${status.total_sent}`} />
          <Stat label="Taux de rebond" value={`${status.bounce_rate} %`} hint={status.bounce_rate > 5 ? "Trop élevé : nettoyer la liste" : "Objectif < 2 %"} />
        </div>
      )}
      {status && !status.mail_configured && (
        <p className="mb-6 rounded-md border border-dashed bg-background p-3 text-sm">Envoi non configuré : renseignez MAIL_USER et MAIL_PASSWORD (Zoho SMTP). Vous pouvez déjà préparer et relire des lots. <Link className="underline" href="/email">Email et délivrabilité</Link></p>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card className="min-w-0">
          <CardHeader className="gap-3">
            <CardTitle className="text-base">1. Choisir les prospects ({selected.length} sélectionné(s))</CardTitle>
            <div className="flex flex-wrap gap-2">
              <Input className="h-8 w-48" placeholder="Nom…" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
              <Input className="h-8 w-36" placeholder="Secteur" value={f.sector} onChange={(e) => setF({ ...f, sector: e.target.value })} />
              <Input className="h-8 w-36" placeholder="Ville" value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })} />
              <Button size="sm" variant="outline" onClick={() => setSelected(Array.from(new Set([...selected, ...(companies?.items || []).map((c) => c.id)])))}>Tout sélectionner</Button>
              <Button size="sm" variant="ghost" onClick={() => setSelected([])}>Vider</Button>
            </div>
            <p className="text-xs text-muted-foreground">Seules les entreprises avec un email public apparaissent. Les adresses « estimées », exclues, déjà contactées depuis moins de 90 jours ou trop peu décrites seront écartées automatiquement, avec la raison.</p>
          </CardHeader>
          <CardContent>
            {companies && !companies.items.length && <Empty>Aucune entreprise avec email. Scannez des sites depuis <Link className="underline" href="/entreprises">Recherche d&apos;entreprises</Link>.</Empty>}
            <ul className="divide-y">
              {companies?.items.map((c) => (
                <li key={c.id} className="flex items-center gap-3 py-2 text-sm">
                  <Checkbox checked={selected.includes(c.id)} onCheckedChange={(v) => toggle(c.id, !!v)} />
                  <ScoreBadge score={c.score} method={c.score_method} />
                  <div className="min-w-0 flex-1">
                    <Link href={`/entreprises/${c.id}`} className="font-medium hover:underline">{c.name}</Link>
                    <div className="truncate text-xs text-muted-foreground">{[c.sector, c.city].filter(Boolean).join(" · ")} · {c.emails} email(s){c.verified_emails ? `, ${c.verified_emails} site officiel` : ""}</div>
                  </div>
                  <StatusBadge status={c.status} />
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Megaphone className="size-4" /> 2. Paramètres du lot</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-1.5"><Label>Nom</Label><Input placeholder="ex. Microfinances Abidjan — novembre" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
              <div className="grid grid-cols-2 gap-2">
                <Select value={form.profile_key} onValueChange={(v) => setForm({ ...form, profile_key: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{Object.entries(PROFILE_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
                </Select>
                <Select value={form.language} onValueChange={(v) => setForm({ ...form, language: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="fr">Français</SelectItem><SelectItem value="en">English</SelectItem></SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5"><Label>Consignes pour l&apos;IA (facultatif)</Label>
                <Textarea rows={3} placeholder="ex. mettre en avant l'automatisation des processus et KORTEX DEFENDER" value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} />
              </div>
              <p className="text-[11px] text-muted-foreground">Pas de pièce jointe dans un premier contact : elles font chuter la délivrabilité. Proposez la plaquette en réponse.</p>
              <Button className="w-full" disabled={!selected.length || busy === "create"} onClick={create}><Spin on={busy === "create"} /> Rédiger {selected.length} email(s)</Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Lots</CardTitle></CardHeader>
            <CardContent className="space-y-1">
              {!campaigns?.length && <p className="text-sm text-muted-foreground">Aucun lot.</p>}
              {campaigns?.map((c) => (
                <Link key={c.id} href={`/campagnes/${c.id}`} className="block rounded-md px-2 py-2 hover:bg-muted">
                  <div className="flex justify-between gap-2 text-sm"><span className="truncate font-medium">{c.name}</span><span className="shrink-0 text-xs text-muted-foreground">{CAMPAIGN_STATUS[c.status]}</span></div>
                  <div className="text-xs text-muted-foreground">{PROFILE_LABELS[c.profile_key]} · {c.counts.envoyee || 0}/{c.total - (c.counts.ignoree || 0)} envoyé(s) · {c.replies} réponse(s) · {fmtDate(c.created_at)}</div>
                </Link>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="gap-1 py-3"><CardContent className="px-4">
      <div className="text-xl font-semibold tabular-nums">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
      {hint && <div className="text-[11px] text-muted-foreground">{hint}</div>}
    </CardContent></Card>
  );
}
