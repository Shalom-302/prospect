"use client";

import Link from "next/link";
import useSWR from "swr";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { APP_STATUS, Application, fetcher, fmtDate, PROFILE_LABELS } from "@/lib/api";
import { Empty, PageHeader } from "@/components/shared";


export default function ApplicationsPage() {
  const { data } = useSWR<Application[]>("/api/applications", fetcher);
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Préparation des candidatures" subtitle="Historique des candidatures et démarches préparées. Rien n'est envoyé sans votre clic dans votre messagerie." />
      {data && !data.length ? <Empty>Aucune candidature. Ouvrez une opportunité ou une entreprise puis « Préparer la candidature ».</Empty> : (
        <Card>
          <CardContent>
            <Table>
              <TableHeader><TableRow><TableHead>Cible</TableHead><TableHead>Profil</TableHead><TableHead>Destinataire</TableHead><TableHead>Statut</TableHead><TableHead>Mise à jour</TableHead></TableRow></TableHeader>
              <TableBody>
                {data?.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell><Link className="font-medium hover:underline" href={`/candidatures/${a.id}`}>{a.target_title}</Link><div className="text-xs text-muted-foreground">{a.target_company}</div></TableCell>
                    <TableCell className="text-sm">{PROFILE_LABELS[a.profile_key]}</TableCell>
                    <TableCell className="text-sm">{a.recipient || <span className="text-muted-foreground">{a.channel === "platform" ? "via la plateforme" : "à renseigner"}</span>}</TableCell>
                    <TableCell className="text-sm">{APP_STATUS[a.status] || a.status}{a.sent_at && <div className="text-xs text-muted-foreground">le {fmtDate(a.sent_at)}</div>}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{fmtDate(a.updated_at, true)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
