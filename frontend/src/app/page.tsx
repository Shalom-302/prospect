"use client";

import Link from "next/link";
import useSWR from "swr";
import { motion } from "framer-motion";
import { ArrowRight, CalendarClock, Clock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Company, fetcher, fmtDate, KIND_LABELS, Opportunity } from "@/lib/api";
import { Empty, PageHeader, ScoreBadge, StatusBadge } from "@/components/shared";

const STATS: [string, string][] = [
  ["companies", "Entreprises découvertes"],
  ["jobs", "Offres d'emploi"],
  ["freelance", "Missions freelance"],
  ["b2b_prospects", "Prospects B2B"],
  ["emails_found", "Emails professionnels"],
  ["letters_generated", "Lettres générées"],
  ["applications_prepared", "Candidatures préparées"],
  ["applications_sent", "Envoyées manuellement"],
  ["replies", "Réponses reçues"],
  ["meetings", "Rendez-vous obtenus"],
];

export default function Dashboard() {
  const { data, error } = useSWR("/api/dashboard", fetcher, { refreshInterval: 60000 });
  const today = new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });

  if (error) return <Empty>API injoignable ({error.message}). Lancez le backend : <code>uvicorn app.main:app</code></Empty>;
  const s = data?.stats || {};
  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title="Bonjour Shalom" subtitle={`${today} · ${s.new_last_24h ?? "…"} nouvelle(s) opportunité(s) depuis 24 h`}>
        <Button asChild variant="outline"><Link href="/offres">Lancer une recherche</Link></Button>
        <Button asChild><Link href="/candidatures">Mes candidatures</Link></Button>
      </PageHeader>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {STATS.map(([k, label], i) => (
          <motion.div key={k} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
            <Card className="gap-1 py-4">
              <CardContent className="px-4">
                <div className="text-2xl font-semibold tabular-nums">{s[k] ?? "–"}</div>
                <div className="text-xs text-muted-foreground">{label}</div>
                {k === "emails_found" && s.emails_verified != null && (
                  <div className="mt-0.5 text-[11px] text-muted-foreground">dont {s.emails_verified} publiés sur site officiel</div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex items-center justify-between">
            <CardTitle className="text-base">Meilleures opportunités à traiter</CardTitle>
            <Link href="/offres" className="text-xs text-muted-foreground hover:underline">Tout voir</Link>
          </CardHeader>
          <CardContent className="space-y-1">
            {!data?.top_opportunities?.length && <p className="text-sm text-muted-foreground">Aucune opportunité. Lancez une recherche.</p>}
            {data?.top_opportunities?.map((o: Opportunity) => (
              <Link key={o.id} href={`/opportunites/${o.id}`} className="flex items-center gap-3 rounded-md px-2 py-2 hover:bg-muted">
                <ScoreBadge score={o.score} method={o.score_method} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{o.title}</div>
                  <div className="truncate text-xs text-muted-foreground">
                    {o.company_name || "Entreprise non précisée"} · {KIND_LABELS[o.kind]} · {o.location || "—"} · {o.source}
                  </div>
                </div>
                <StatusBadge status={o.status} />
              </Link>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2 text-base"><CalendarClock className="size-4" /> Actions à faire</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {!data?.due_actions?.length && !data?.deadlines?.length && <p className="text-sm text-muted-foreground">Rien d&apos;urgent.</p>}
              {data?.due_actions?.map((a: any) => (
                <Link key={a.type + a.id} href={a.type === "company" ? `/entreprises/${a.id}` : `/opportunites/${a.id}`} className="block rounded-md border p-2 hover:bg-muted">
                  <div className="text-sm font-medium">{a.action || "Action"}</div>
                  <div className="text-xs text-muted-foreground">{a.title} · {fmtDate(a.date)}</div>
                </Link>
              ))}
              {data?.deadlines?.map((o: Opportunity) => (
                <Link key={"d" + o.id} href={`/opportunites/${o.id}`} className="block rounded-md border border-dashed p-2 hover:bg-muted">
                  <div className="flex items-center gap-1 text-sm font-medium"><Clock className="size-3.5" /> Date limite {fmtDate(o.deadline)}</div>
                  <div className="text-xs text-muted-foreground">{o.title}</div>
                </Link>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle className="text-base">Prospects B2B prioritaires</CardTitle>
              <Link href="/b2b" className="text-xs text-muted-foreground hover:underline">Tout voir</Link>
            </CardHeader>
            <CardContent className="space-y-1">
              {!data?.top_companies?.length && <p className="text-sm text-muted-foreground">Aucun prospect qualifié.</p>}
              {data?.top_companies?.map((c: Company) => (
                <Link key={c.id} href={`/entreprises/${c.id}`} className="flex items-center gap-3 rounded-md px-2 py-1.5 hover:bg-muted">
                  <ScoreBadge score={c.score} method={c.score_method} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm">{c.name}</div>
                    <div className="truncate text-xs text-muted-foreground">{[c.sector, c.city].filter(Boolean).join(" · ")} · {c.emails} email(s)</div>
                  </div>
                  <ArrowRight className="size-3.5 text-muted-foreground" />
                </Link>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>

      <Card className="mt-6">
        <CardHeader><CardTitle className="text-base">Activité récente</CardTitle></CardHeader>
        <CardContent>
          <ul className="divide-y text-sm">
            {data?.recent_activity?.map((a: any) => (
              <li key={a.id} className="flex justify-between gap-4 py-2">
                <span className="truncate">{a.summary}</span>
                <span className="shrink-0 text-xs text-muted-foreground">{fmtDate(a.occurred_at, true)}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
