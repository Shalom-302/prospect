"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Company, DOC_TYPE_LABELS, fetcher, fmtDate, Generated, Opportunity, PROFILE_LABELS } from "@/lib/api";
import { Empty, PageHeader, ScoreBadge } from "@/components/shared";
import { GeneratorPanel } from "@/components/generator-panel";

type Target = { type: "opportunity"; item: Opportunity } | { type: "company"; item: Company };

export function GeneratorHub({ mode }: { mode: "letters" | "emails" }) {
  const [tab, setTab] = useState<"opportunity" | "company">("opportunity");
  const [q, setQ] = useState("");
  const [target, setTarget] = useState<Target | null>(null);
  const { data: opps } = useSWR<{ items: Opportunity[] }>(tab === "opportunity" ? `/api/opportunities?limit=30&q=${encodeURIComponent(q)}` : null, fetcher);
  const { data: comps } = useSWR<{ items: Company[] }>(tab === "company" ? `/api/companies?limit=30&q=${encodeURIComponent(q)}` : null, fetcher);
  const docTypes = mode === "letters" ? "cover_letter,b2b_proposal" : "email";
  const { data: recent } = useSWR<Generated[]>(`/api/generated?doc_type=${docTypes}&limit=30`, fetcher);

  const isKortex = target?.type === "company" || (target?.type === "opportunity" && (target.item.profile_key === "kortex" || target.item.kind === "b2b"));
  const types: Generated["doc_type"][] = mode === "emails" ? ["email"] : isKortex ? ["b2b_proposal", "cover_letter"] : ["cover_letter", "b2b_proposal"];

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title={mode === "letters" ? "Générateur de lettres" : "Générateur d'emails"}
        subtitle={mode === "letters"
          ? "Lettres de motivation (Shalom) et propositions commerciales (KORTEX), écrites à partir de l'annonce ou de l'entreprise et de vos documents réels."
          : "Emails d'accompagnement courts : objet, présentation, proposition, appel à l'action, signature."} />
      <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader className="gap-3">
            <CardTitle className="text-base">1. Choisir la cible</CardTitle>
            <Tabs value={tab} onValueChange={(v) => setTab(v as any)}>
              <TabsList className="w-full"><TabsTrigger value="opportunity">Opportunité</TabsTrigger><TabsTrigger value="company">Entreprise</TabsTrigger></TabsList>
            </Tabs>
            <Input placeholder="Rechercher…" value={q} onChange={(e) => setQ(e.target.value)} />
          </CardHeader>
          <CardContent className="max-h-[520px] space-y-1 overflow-y-auto">
            {tab === "opportunity" && opps?.items.map((o) => (
              <button key={o.id} onClick={() => setTarget({ type: "opportunity", item: o })}
                className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted ${target?.type === "opportunity" && target.item.id === o.id ? "bg-muted" : ""}`}>
                <ScoreBadge score={o.score} method={o.score_method} />
                <span className="min-w-0 flex-1"><span className="block truncate">{o.title}</span><span className="block truncate text-xs text-muted-foreground">{o.company_name}</span></span>
              </button>
            ))}
            {tab === "company" && comps?.items.map((c) => (
              <button key={c.id} onClick={() => setTarget({ type: "company", item: c })}
                className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted ${target?.type === "company" && target.item.id === c.id ? "bg-muted" : ""}`}>
                <ScoreBadge score={c.score} method={c.score_method} />
                <span className="min-w-0 flex-1 truncate">{c.name}</span>
              </button>
            ))}
          </CardContent>
        </Card>
        <div className="space-y-6">
          {target ? (
            <>
              <div className="text-sm">
                2. Cible : <Link className="font-medium underline" href={target.type === "company" ? `/entreprises/${target.item.id}` : `/opportunites/${target.item.id}`}>
                  {target.type === "company" ? target.item.name : `${target.item.title} — ${target.item.company_name}`}</Link>
              </div>
              <GeneratorPanel key={target.type + target.item.id}
                opportunityId={target.type === "opportunity" ? target.item.id : null}
                companyId={target.type === "company" ? target.item.id : null}
                defaultProfile={isKortex ? "kortex" : "shalom"}
                defaultLanguage={target.type === "opportunity" ? target.item.language || "fr" : "fr"} types={types} />
            </>
          ) : <Empty>Sélectionnez une opportunité ou une entreprise : aucune lettre générique n&apos;est produite.</Empty>}
          <Card>
            <CardHeader><CardTitle className="text-base">Derniers documents générés</CardTitle></CardHeader>
            <CardContent>
              <ul className="divide-y text-sm">
                {recent?.map((g) => (
                  <li key={g.id} className="flex flex-wrap items-center gap-2 py-2">
                    <span className="font-medium">{g.subject || DOC_TYPE_LABELS[g.doc_type]}</span>
                    <span className="text-xs text-muted-foreground">{DOC_TYPE_LABELS[g.doc_type]} · {PROFILE_LABELS[g.profile_key]} · {g.language.toUpperCase()} · {fmtDate(g.created_at, true)}</span>
                    <Link className="ml-auto text-xs underline" href={g.opportunity_id ? `/opportunites/${g.opportunity_id}` : `/entreprises/${g.company_id}`}>Ouvrir</Link>
                  </li>
                ))}
                {!recent?.length && <li className="py-2 text-xs text-muted-foreground">Aucun pour l&apos;instant.</li>}
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
