"use client";

import Link from "next/link";
import { use, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { AlertTriangle, ArrowLeft, Pause, Play, RefreshCw, Send, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api, fetcher, fmtDate, PROFILE_LABELS } from "@/lib/api";
import { PageHeader, Spin, useAction } from "@/components/shared";

const CAMPAIGN_STATUS: Record<string, string> = {
  generating: "Rédaction en cours", review: "À relire et valider", sending: "Envoi en cours", paused: "En pause", done: "Terminé",
};
const ITEM_STATUS: Record<string, string> = {
  brouillon: "À relire", approuvee: "En file d'envoi", envoyee: "Envoyé", echec: "Échec", ignoree: "Écarté",
};

export default function CampaignPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data: c, mutate } = useSWR<any>(`/api/campaigns/${id}`, fetcher, {
    refreshInterval: (d) => (d && ["generating", "sending"].includes(d.status) ? 5000 : 0),
  });
  const { busy, run } = useAction();
  const [showIgnored, setShowIgnored] = useState(false);

  if (!c) return <p className="text-sm text-muted-foreground">Chargement…</p>;
  const active = c.items.filter((i: any) => i.status !== "ignoree");
  const ignored = c.items.filter((i: any) => i.status === "ignoree");
  const toReview = c.items.filter((i: any) => i.status === "brouillon");
  const warnings = toReview.filter((i: any) => i.warnings.length).length;

  async function approve() {
    if (!confirm(`Valider l'envoi de ${toReview.length} email(s) depuis contact@kortexdigital.net ?\n\nIls partiront un par un, espacés de quelques minutes, en heures ouvrées, dans la limite du plafond quotidien. Vous pourrez mettre en pause à tout moment.`)) return;
    const r = await run("approve", () => api(`/api/campaigns/${id}/approve`, { method: "POST" }));
    if (r) { toast.success(r.message); mutate(); }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <Link href="/campagnes" className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"><ArrowLeft className="size-3.5" /> Campagnes</Link>
      <PageHeader title={c.name} subtitle={`${PROFILE_LABELS[c.profile_key]} · ${c.language.toUpperCase()} · ${CAMPAIGN_STATUS[c.status]}`}>
        {c.status === "review" && <Button onClick={approve} disabled={!toReview.length || busy === "approve"}><Spin on={busy === "approve"} /><Send className="size-4" /> Valider et programmer l&apos;envoi ({toReview.length})</Button>}
        {c.status === "sending" && <Button variant="outline" onClick={() => run("p", () => api(`/api/campaigns/${id}/pause`, { method: "POST" })).then(() => mutate())}><Pause className="size-4" /> Pause</Button>}
        {c.status === "paused" && <Button onClick={() => run("r", () => api(`/api/campaigns/${id}/resume`, { method: "POST" })).then(() => mutate())}><Play className="size-4" /> Reprendre</Button>}
        {!c.counts.envoyee && <Button variant="ghost" onClick={() => confirm("Supprimer ce lot ?") && run("d", () => api(`/api/campaigns/${id}`, { method: "DELETE" })).then(() => router.push("/campagnes"))}><Trash2 className="size-4" /></Button>}
      </PageHeader>

      {c.status === "generating" && <p className="mb-4 flex items-center gap-2 text-sm"><Spin on /> L&apos;IA rédige les emails ({c.items.filter((i: any) => i.body).length}/{active.length})…</p>}
      {c.paused_reason && <p className="mb-4 flex items-center gap-2 rounded-md border border-dashed bg-background p-3 text-sm"><AlertTriangle className="size-4" /> {c.paused_reason}</p>}
      <div className="mb-6 flex flex-wrap gap-4 text-sm">
        {Object.entries(c.counts).map(([k, v]) => <span key={k}><b className="tabular-nums">{v as number}</b> {ITEM_STATUS[k] || k}</span>)}
        <span><b>{c.replies}</b> réponse(s)</span><span><b>{c.bounces}</b> rebond(s)</span>
        {c.status === "sending" && c.next_send_at && <span className="text-muted-foreground">prochain envoi ≥ {fmtDate(c.next_send_at, true)}</span>}
      </div>
      {c.status === "review" && (
        <p className="mb-4 text-xs text-muted-foreground">
          Relisez chaque email. {warnings ? `${warnings} email(s) ont des points d'attention.` : "Aucun point d'attention détecté."} Un pied de page de désinscription est ajouté automatiquement à l&apos;envoi.
        </p>
      )}

      <div className="space-y-4">
        {active.map((i: any) => <ItemCard key={`${i.id}-${i.body ? "b" : "e"}`} campaignId={id} item={i} editable={["brouillon", "approuvee"].includes(i.status)} onChange={() => mutate()} />)}
      </div>

      {!!ignored.length && (
        <Card className="mt-6">
          <CardHeader className="flex items-center justify-between">
            <CardTitle className="text-base">{ignored.length} prospect(s) écarté(s)</CardTitle>
            <Button size="sm" variant="ghost" onClick={() => setShowIgnored(!showIgnored)}>{showIgnored ? "Masquer" : "Voir"}</Button>
          </CardHeader>
          {showIgnored && (
            <CardContent>
              <ul className="divide-y text-sm">
                {ignored.map((i: any) => (
                  <li key={i.id} className="flex flex-wrap items-center gap-2 py-2">
                    <span className="font-medium">{i.target}</span><span className="text-xs text-muted-foreground">{i.recipient || "pas d'email"}</span>
                    <span className="min-w-0 flex-1 text-xs text-muted-foreground">— {i.error}</span>
                    {i.body && i.recipient && <Button size="sm" variant="ghost" onClick={() => run("inc", () => api(`/api/campaigns/${id}/items/${i.id}`, { method: "PATCH", json: { include: true } })).then(() => mutate())}>Réintégrer</Button>}
                  </li>
                ))}
              </ul>
            </CardContent>
          )}
        </Card>
      )}
    </div>
  );
}

function ItemCard({ campaignId, item, editable, onChange }: { campaignId: string; item: any; editable: boolean; onChange: () => void }) {
  const [form, setForm] = useState({ recipient: item.recipient, subject: item.subject, body: item.body });
  const dirty = form.recipient !== item.recipient || form.subject !== item.subject || form.body !== item.body;
  const { busy, run } = useAction();
  const path = `/api/campaigns/${campaignId}/items/${item.id}`;
  return (
    <Card className="gap-3">
      <CardHeader className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <CardTitle className="truncate text-sm">
            {item.company_id ? <Link className="hover:underline" href={`/entreprises/${item.company_id}`}>{item.target}</Link> : item.target}
          </CardTitle>
          <div className="text-xs text-muted-foreground">{item.target_title} · {ITEM_STATUS[item.status]}{item.sent_at ? ` le ${fmtDate(item.sent_at, true)}` : ""}{item.delivery ? ` · ${item.delivery === "replied" ? "a répondu" : item.delivery === "bounced" ? "rebond" : "désinscrit"}` : ""}</div>
        </div>
        {editable && (
          <label className="flex shrink-0 items-center gap-2 text-xs">Inclure
            <Switch checked onCheckedChange={(v) => !v && run("x", () => api(path, { method: "PATCH", json: { include: false } })).then(onChange)} />
          </label>
        )}
      </CardHeader>
      <CardContent className="space-y-2">
        {!item.body ? <p className="flex items-center gap-2 text-sm text-muted-foreground"><Spin on /> Rédaction…</p> : (
          <>
            <Input disabled={!editable} value={form.recipient} onChange={(e) => setForm({ ...form, recipient: e.target.value })} className="h-8 text-sm" />
            <Input disabled={!editable} value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} className="h-8 font-medium" />
            <Textarea disabled={!editable} rows={9} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} className="text-[13px] leading-relaxed" />
            {!!item.warnings.length && (
              <ul className="space-y-0.5 text-xs">{item.warnings.map((w: string) => <li key={w} className="flex items-center gap-1"><AlertTriangle className="size-3" /> {w}</li>)}</ul>
            )}
            {item.error && <p className="text-xs text-muted-foreground">{item.error}</p>}
            {editable && (
              <div className="flex gap-2">
                <Button size="sm" variant={dirty ? "default" : "outline"} disabled={!dirty || busy === "s"}
                  onClick={() => run("s", () => api(path, { method: "PATCH", json: form }), "Enregistré").then(onChange)}>Enregistrer</Button>
                <Button size="sm" variant="ghost" disabled={busy === "g"}
                  onClick={() => run("g", () => api(`${path}/regenerate`, { method: "POST" }), "Nouvelle version").then((r: any) => { if (r) { setForm({ recipient: r.recipient, subject: r.subject, body: r.body }); onChange(); } })}>
                  <Spin on={busy === "g"} /><RefreshCw className="size-3.5" /> Réécrire
                </Button>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
