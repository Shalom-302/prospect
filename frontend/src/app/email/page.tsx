"use client";

import { useState } from "react";
import useSWR from "swr";
import { CheckCircle2, CircleAlert, Inbox, Mail, Plug, ShieldCheck, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, fetcher, fmtDate } from "@/lib/api";
import { PageHeader, Spin, useAction } from "@/components/shared";

export default function EmailPage() {
  const { data: zoho, mutate: mz } = useSWR<any>("/api/email/status", fetcher);
  const { data: st, mutate: ms } = useSWR<any>("/api/outreach/status", fetcher);
  const { data: sup, mutate: msup } = useSWR<any[]>("/api/outreach/suppressions", fetcher);
  const [newSup, setNewSup] = useState("");
  const { busy, run } = useAction();

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader title="Email et délivrabilité" subtitle={st ? `Expéditeur : ${st.sender}` : "contact@kortexdigital.net"} />

      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="size-4" /> Authentification du domaine</CardTitle>
          <Button size="sm" variant="outline" onClick={() => ms()}>Revérifier</Button>
        </CardHeader>
        <CardContent>
          <p className="mb-3 text-xs text-muted-foreground">Gmail, Outlook et Yahoo exigent SPF, DKIM et DMARC pour ne pas classer vos emails en spam.</p>
          <ul className="divide-y">
            {st?.dns?.map((d: any) => (
              <li key={d.key} className="flex gap-3 py-2 text-sm">
                {d.ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0" /> : <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" />}
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{d.label}</div>
                  {d.value && <div className="truncate font-mono text-[11px] text-muted-foreground">{d.value}</div>}
                  <div className="text-xs">{d.advice}</div>
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Plug className="size-4" /> Envoi par lots (SMTP) et suivi des réponses (IMAP)</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-sm">
          {st && !st.mail_configured ? (
            <ol className="list-decimal space-y-1 pl-5 text-muted-foreground">
              <li>Zoho Mail › Paramètres › Comptes de messagerie : activez l&apos;accès <b>IMAP</b> (SMTP est inclus). L&apos;offre gratuite Zoho ne permet pas IMAP/SMTP : il faut une offre payante (Mail Lite ou plus).</li>
              <li>Si la double authentification est active : Zoho Accounts › Sécurité › <b>Mots de passe d&apos;application</b> › en créer un « KORTEX Prospect ».</li>
              <li>Dans l&apos;environnement (Dokploy ou .env) : <code>MAIL_USER=contact@kortexdigital.net</code> et <code>MAIL_PASSWORD=&lt;mot de passe d&apos;application&gt;</code>. Serveurs par défaut : smtppro.zoho.com / imappro.zoho.com (remplacer .com par .eu si le compte est hébergé en Europe).</li>
            </ol>
          ) : st && (
            <div className="grid gap-2 sm:grid-cols-2">
              <div>SMTP : <b>{st.smtp_host}</b> · IMAP : <b>{st.imap_host}</b></div>
              <div>Rythme : {st.sent_today}/{st.daily_limit} aujourd&apos;hui ({st.phase}), un email toutes les {Math.round(st.interval[0] / 60)}–{Math.round(st.interval[1] / 60)} min, {st.hours} h en semaine</div>
              <div>Pas de recontact avant {st.recontact_days} jours · {st.suppressions} adresse(s) exclue(s)</div>
              <div>Réponses : {st.reply_rate} % · Rebonds : {st.bounce_rate} % ({st.bounced}/{st.total_sent})</div>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" disabled={busy === "t"} onClick={() => run("t", () => api("/api/outreach/test-connection", { method: "POST" })).then((r: any) => r && (r.ok ? toast.success(r.message) : toast.error(r.message)))}>
              <Spin on={busy === "t"} /> Tester la connexion
            </Button>
            <Button size="sm" variant="outline" disabled={busy === "i" || !st?.mail_configured} onClick={() => run("i", () => api("/api/outreach/scan-inbox", { method: "POST" }), (r: any) => `${r.replies} réponse(s), ${r.bounces} rebond(s) détecté(s)`).then(() => ms())}>
              <Spin on={busy === "i"} /><Inbox className="size-3.5" /> Analyser la boîte de réception
            </Button>
          </div>
          <div className="rounded-md bg-muted/50 p-3 text-xs">
            <div className="mb-1 font-medium">Ce que fait l&apos;application pour rester en boîte de réception</div>
            <ul className="list-disc space-y-0.5 pl-4">
              <li>Montée en charge : 10 emails/jour la 1re semaine, 20 la 2e, puis 30 maximum.</li>
              <li>Un email à la fois, espacé aléatoirement, uniquement en heures ouvrées d&apos;Abidjan.</li>
              <li>Texte brut, court, personnalisé par l&apos;IA pour chaque entreprise ; pas de pièce jointe ni de pixel de suivi.</li>
              <li>Désinscription en un clic (en-tête List-Unsubscribe) et liste d&apos;exclusion définitive.</li>
              <li>Lecture des réponses et rebonds : arrêt des envois vers qui répond, pause automatique au-delà de 5 % de rebonds.</li>
            </ul>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Liste d&apos;exclusion</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input placeholder="adresse@entreprise.ci" value={newSup} onChange={(e) => setNewSup(e.target.value)} />
            <Button variant="outline" disabled={!newSup.includes("@")} onClick={() => run("a", () => api("/api/outreach/suppressions", { method: "POST", json: { email: newSup } }), "Ajoutée").then(() => { setNewSup(""); msup(); })}>Exclure</Button>
          </div>
          <ul className="divide-y text-sm">
            {sup?.map((x) => (
              <li key={x.id} className="flex items-center gap-3 py-1.5">
                <span className="flex-1 truncate">{x.email}</span>
                <span className="text-xs text-muted-foreground">{({ unsubscribe: "désinscription", bounce: "rebond", stop: "réponse STOP", refus: "refus", manual: "manuel" } as any)[x.reason] || x.reason} · {fmtDate(x.created_at)}</span>
                <button onClick={() => confirm(`Retirer ${x.email} de la liste d'exclusion ?`) && run("d", () => api(`/api/outreach/suppressions/${x.id}`, { method: "DELETE" })).then(() => msup())}><Trash2 className="size-3.5 text-muted-foreground" /></button>
              </li>
            ))}
            {!sup?.length && <li className="py-1.5 text-xs text-muted-foreground">Aucune adresse exclue.</li>}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Mail className="size-4" /> Brouillons Zoho Mail (candidatures individuelles)</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-sm">
          {!zoho?.configured && <p className="text-muted-foreground">Facultatif. API Zoho (api-console.zoho.com › Server-based Application) avec l&apos;URI de retour <code>{typeof window !== "undefined" ? location.origin : ""}/api/email/zoho/callback</code>, puis ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET. Sans cela, le brouillon .eml fonctionne.</p>}
          {zoho?.configured && !zoho?.connected && (
            <Button onClick={() => run("c", () => api("/api/email/zoho/authorize")).then((r: any) => r && (location.href = r.url))}>Connecter mon compte Zoho</Button>
          )}
          {zoho?.connected && (
            <div className="flex items-center gap-3"><CheckCircle2 className="size-4" /> Connecté : <b>{zoho.email}</b>
              <Button size="sm" variant="outline" className="ml-auto" onClick={() => run("d", () => api("/api/email/zoho", { method: "DELETE" }), "Déconnecté").then(() => mz())}>Déconnecter</Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
