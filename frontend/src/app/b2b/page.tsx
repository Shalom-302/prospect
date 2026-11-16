"use client";

import Link from "next/link";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OpportunityExplorer } from "@/components/opportunity-explorer";
import { ScoreBadge } from "@/components/shared";
import { Company, fetcher } from "@/lib/api";

export default function Page() {
  const { data } = useSWR<{ items: Company[] }>("/api/companies?min_score=55&limit=12", fetcher);
  return (
    <OpportunityExplorer kind="b2b" title="Opportunités B2B" subtitle="Appels d'offres, besoins de prestataires et sous-traitance pour KORTEX DIGITAL.">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Prospects entreprises qualifiés</CardTitle>
          <p className="text-xs text-muted-foreground">Entreprises sans besoin publié : à approcher avec une proposition commerciale.</p>
        </CardHeader>
        <CardContent className="space-y-1">
          {!data?.items?.length && <p className="text-sm text-muted-foreground">Aucun. Voir <Link className="underline" href="/entreprises">Recherche d&apos;entreprises</Link>.</p>}
          {data?.items?.map((c) => (
            <Link key={c.id} href={`/entreprises/${c.id}`} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted">
              <ScoreBadge score={c.score} method={c.score_method} />
              <span className="flex-1 truncate">{c.name}</span>
              <span className="text-xs text-muted-foreground">{c.emails} email(s)</span>
            </Link>
          ))}
        </CardContent>
      </Card>
    </OpportunityExplorer>
  );
}
