"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { ArrowLeft, CheckCheck, ExternalLink, FileDown, Mail, Save, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, APP_STATUS, Doc, DOC_TYPE_LABELS, download, fetcher, fmtDate, Generated, PROFILE_LABELS } from "@/lib/api";
import { ConfidenceBadge, PageHeader, Spin, useAction } from "@/components/shared";

export default function ApplicationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: a, mutate } = useSWR<any>(`/api/applications/${id}`, fetcher);
  const { data: docs } = useSWR<Doc[]>("/api/documents", fetcher);
  const genQs = a ? (a.opportunity_id ? `opportunity_id=${a.opportunity_id}` : `company_id=${a.company_id}`) : null;
  const { data: generated } = useSWR<Generated[]>(genQs ? `/api/generated?${genQs}` : null, fetcher);
  const { data: email } = useSWR<any>("/api/email/status", fetcher);
  const [form, setForm] = useState<any>(null);
  const [checks, setChecks] = useState({ recipient: false, content: false, attachments: false });
  const { busy, run } = useAction();

  useEffect(() => {
    if (a && !form) setForm({ recipient: a.recipient, cc: a.cc, subject: a.subject, body: a.body, letter_id: a.letter_id, attachment_ids: a.attachment_ids, attach_letter_format: a.attach_letter_format });
  }, [a, form]);

  if (!a || !form) return <p className="text-sm text-muted-foreground">Chargement…</p>;

  const dirty = JSON.stringify(form) !== JSON.stringify({ recipient: a.recipient, cc: a.cc, subject: a.subject, body: a.body, letter_id: a.letter_id, attachment_ids: a.attachment_ids, attach_letter_format: a.attach_letter_format });
  const allChecked = checks.recipient && checks.content && checks.attachments;
  const save = async (silent = false) => {
    const r = await run("save", () => api(`/api/applications/${id}`, { method: "PATCH", json: form }), silent ? undefined : "Brouillon enregistré");
    await mutate();
    return r;
  };
  const resetChecks = () => setChecks({ recipient: false, content: false, attachments: false });
  const set = (patch: object) => { setForm({ ...form, ...patch }); resetChecks(); };

  const letters = (generated || []).filter((g) => g.doc_type !== "email");
  const emails = (generated || []).filter((g) => g.doc_type === "email");
  const recIds = new Set(a.recommendations.filter((r: any) => r.document_id).map((r: any) => r.document_id));
  const recipientInfo = a.company?.emails?.find((e: any) => e.value === form.recipient);
  const targetHref = a.opportunity_id ? `/opportunites/${a.opportunity_id}` : `/entreprises/${a.company_id}`;
  const visibleDocs = (docs || []).filter((d) => !d.profile_key || d.profile_key === a.profile_key);

  async function prepareThen(action: () => Promise<void>) {
    if (dirty) await save(true);
    await action();
    mutate();
  }

  return (
    <div className="mx-auto max-w-6xl">
      <Link href="/candidatures" className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"><ArrowLeft className="size-3.5" /> Candidatures</Link>
      <PageHeader title={a.opportunity?.title || a.company?.name || "Candidature"}
        subtitle={`${PROFILE_LABELS[a.profile_key]} · ${APP_STATUS[a.status] || a.status}${a.sent_at ? ` le ${fmtDate(a.sent_at)}` : ""}`}>
        <Button variant="outline" asChild><Link href={targetHref}>Voir la fiche</Link></Button>
        <Button variant={dirty ? "default" : "outline"} onClick={() => save()} disabled={!dirty || busy === "save"}><Save className="size-4" /> Enregistrer</Button>
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="text-base">Email</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-1.5">
                <Label>Destinataire</Label>
                <Input value={form.recipient} onChange={(e) => set({ recipient: e.target.value })} placeholder="adresse@entreprise.ci" />
                {recipientInfo && <div className="flex items-center gap-2 text-xs"><ConfidenceBadge confidence={recipientInfo.confidence} />{recipientInfo.source_url && <a className="underline text-muted-foreground" href={recipientInfo.source_url} target="_blank" rel="noreferrer">source</a>}</div>}
                {form.recipient && !recipientInfo && <p className="text-xs text-muted-foreground">Adresse saisie manuellement : vérifiez-la.</p>}
                {!!a.company?.emails?.length && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {a.company.emails.map((e: any) => (
                      <button key={e.value} onClick={() => set({ recipient: e.value })} className="rounded border px-2 py-0.5 text-xs hover:bg-muted">{e.value} <span className="text-muted-foreground">({e.label})</span></button>
                    ))}
                  </div>
                )}
                {!a.company?.emails?.length && (
                  <p className="text-xs text-muted-foreground">
                    Aucun email public connu.{" "}
                    {a.opportunity?.apply_url && <>Postulez via <a className="underline" href={a.opportunity.apply_url} target="_blank" rel="noreferrer">la page de candidature</a>. </>}
                    {a.company?.forms?.map((f: string) => <a key={f} className="mr-2 underline" href={f} target="_blank" rel="noreferrer">formulaire / carrières</a>)}
                  </p>
                )}
              </div>
              <div className="space-y-1.5"><Label>Cc</Label><Input value={form.cc} onChange={(e) => set({ cc: e.target.value })} /></div>
              {!!emails.length && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-muted-foreground">Reprendre un email généré :</span>
                  {emails.map((g) => <button key={g.id} className="underline" onClick={() => set({ subject: g.subject, body: g.content })}>{fmtDate(g.created_at, true)} ({g.language})</button>)}
                </div>
              )}
              <div className="space-y-1.5"><Label>Objet</Label><Input value={form.subject} onChange={(e) => set({ subject: e.target.value })} /></div>
              <div className="space-y-1.5"><Label>Message</Label><Textarea rows={14} value={form.body} onChange={(e) => set({ body: e.target.value })} /></div>
              {!emails.length && <p className="text-xs text-muted-foreground">Pas encore d&apos;email généré : <Link className="underline" href={targetHref}>générez-le depuis la fiche</Link>, ou rédigez-le ici.</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle className="text-base">Pièces jointes</CardTitle>
              <Button size="sm" variant="outline" onClick={() => set({ attachment_ids: Array.from(new Set([...form.attachment_ids, ...recIds])) })}>Ajouter les recommandées</Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-md bg-muted/50 p-3 text-xs">
                <div className="mb-1 font-medium">Recommandations</div>
                <ul className="space-y-0.5">{a.recommendations.map((r: any, i: number) => <li key={i}>• <b>{r.title}</b> — {r.reason}</li>)}</ul>
              </div>
              <div className="space-y-2">
                <Label>Lettre / proposition à joindre</Label>
                <div className="flex gap-2">
                  <Select value={form.letter_id ? String(form.letter_id) : "none"} onValueChange={(v) => set({ letter_id: v === "none" ? null : Number(v), attach_letter_format: v === "none" ? "none" : form.attach_letter_format === "none" ? "pdf" : form.attach_letter_format })}>
                    <SelectTrigger className="flex-1"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Aucune</SelectItem>
                      {letters.map((g) => <SelectItem key={g.id} value={String(g.id)}>{DOC_TYPE_LABELS[g.doc_type]} · {g.language.toUpperCase()} · {fmtDate(g.updated_at, true)}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  {form.letter_id && (
                    <Select value={form.attach_letter_format} onValueChange={(v) => set({ attach_letter_format: v })}>
                      <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
                      <SelectContent><SelectItem value="pdf">PDF</SelectItem><SelectItem value="docx">DOCX</SelectItem><SelectItem value="none">Ne pas joindre</SelectItem></SelectContent>
                    </Select>
                  )}
                  {form.letter_id && <Button variant="outline" size="icon" onClick={() => run("dl", () => download(`/api/generated/${form.letter_id}/export?format=pdf`))}><FileDown className="size-4" /></Button>}
                </div>
              </div>
              <div className="space-y-1">
                <Label>Documents de la bibliothèque</Label>
                <ul className="divide-y rounded-md border">
                  {visibleDocs.map((d) => (
                    <li key={d.id} className="flex items-center gap-3 px-3 py-2 text-sm">
                      <Checkbox checked={form.attachment_ids.includes(d.id)}
                        onCheckedChange={(v) => set({ attachment_ids: v ? [...form.attachment_ids, d.id] : form.attachment_ids.filter((x: number) => x !== d.id) })} />
                      <span className="min-w-0 flex-1 truncate">{d.title} <span className="text-xs text-muted-foreground">· {d.category_label} · {d.language.toUpperCase()}</span></span>
                      {recIds.has(d.id) && <span className="rounded bg-primary px-1.5 text-[10px] text-primary-foreground">recommandé</span>}
                    </li>
                  ))}
                </ul>
                <p className="text-[11px] text-muted-foreground">Aucune pièce n&apos;est jointe sans être cochée ici.</p>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="lg:sticky lg:top-6">
            <CardHeader><CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="size-4" /> Vérification avant envoi</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2 text-sm">
                {([["recipient", `J'ai vérifié le destinataire${form.recipient ? ` (${form.recipient})` : ""}`], ["content", "J'ai relu l'objet et le message"],
                   ["attachments", `J'ai validé les pièces jointes (${form.attachment_ids.length + (form.letter_id && form.attach_letter_format !== "none" ? 1 : 0)})`]] as const).map(([k, label]) => (
                  <label key={k} className="flex items-start gap-2">
                    <Checkbox className="mt-0.5" checked={(checks as any)[k]} onCheckedChange={(v) => setChecks({ ...checks, [k]: !!v })} /> {label}
                  </label>
                ))}
              </div>
              <div className="space-y-2 border-t pt-4">
                <Button className="w-full" disabled={!allChecked || busy === "eml"}
                  onClick={() => prepareThen(async () => { await run("eml", () => download(`/api/applications/${id}/eml`, "brouillon.eml"), "Brouillon .eml téléchargé : ouvrez-le, vérifiez, puis cliquez Envoyer"); })}>
                  <Spin on={busy === "eml"} /><FileDown className="size-4" /> Brouillon .eml (avec pièces jointes)
                </Button>
                <Button className="w-full" variant="outline" disabled={!allChecked || !email?.connected || busy === "zoho"}
                  onClick={() => prepareThen(async () => {
                    const r = await run("zoho", () => api(`/api/applications/${id}/zoho-draft`, { method: "POST" }));
                    if (r) { toast.success("Brouillon créé dans Zoho Mail (non envoyé)"); window.open(r.open_url, "_blank"); }
                  })}>
                  <Spin on={busy === "zoho"} /><Mail className="size-4" /> Brouillon Zoho Mail
                </Button>
                {!email?.connected && <p className="text-[11px] text-muted-foreground">Zoho non connecté — <Link className="underline" href="/email">connexion email</Link>.</p>}
                <Button className="w-full" variant="ghost" disabled={!allChecked}
                  onClick={() => prepareThen(async () => {
                    const r = await run("mailto", () => api(`/api/applications/${id}/mailto`));
                    if (r) { toast.message(r.warning); window.location.href = r.url; }
                  })}>
                  <ExternalLink className="size-4" /> Ouvrir dans ma messagerie (sans PJ)
                </Button>
                {!allChecked && <p className="text-[11px] text-muted-foreground">Cochez les trois vérifications pour préparer le brouillon.</p>}
              </div>
              <div className="border-t pt-4">
                <p className="mb-2 text-xs text-muted-foreground">Après avoir cliqué vous-même sur « Envoyer » dans votre messagerie (ou postulé sur la plateforme) :</p>
                <Button className="w-full" variant={a.status === "envoyee" ? "outline" : "default"} disabled={a.status === "envoyee" || busy === "sent"}
                  onClick={() => confirm("Confirmez-vous avoir envoyé cette candidature vous-même ?") && run("sent", () => api(`/api/applications/${id}/mark-sent`, { method: "POST", json: { follow_up_days: 7 } }), "Envoi enregistré · relance prévue dans 7 jours").then(() => mutate())}>
                  <CheckCheck className="size-4" /> {a.status === "envoyee" ? `Envoyée le ${fmtDate(a.sent_at)}` : "Confirmer l'envoi manuel"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
