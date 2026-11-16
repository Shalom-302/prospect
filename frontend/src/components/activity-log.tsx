"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Activity, api, fmtDate } from "@/lib/api";
import { useAction } from "@/components/shared";

const TYPES: Record<string, string> = {
  note: "Note",
  reply: "Réponse reçue",
  meeting: "Rendez-vous programmé",
  interview: "Entretien réalisé",
  follow_up: "Relance effectuée",
};
const LABELS: Record<string, string> = { ...TYPES, status_change: "Statut", generated: "Génération", email_sent: "Envoi manuel" };

export function ActivityLog({ activities, companyId, opportunityId, onChange }: { activities: Activity[]; companyId?: number | null; opportunityId?: number | null; onChange: () => void }) {
  const [type, setType] = useState("note");
  const [summary, setSummary] = useState("");
  const { run } = useAction();
  async function add() {
    if (!summary.trim()) return;
    await run("add", () => api("/api/activities", { method: "POST", json: { type, summary, company_id: companyId || null, opportunity_id: opportunityId || null } }), "Ajouté à l'historique");
    setSummary("");
    onChange();
  }
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Historique des échanges</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-col gap-2 sm:flex-row">
          <Select value={type} onValueChange={setType}>
            <SelectTrigger className="sm:w-48"><SelectValue /></SelectTrigger>
            <SelectContent>{Object.entries(TYPES).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
          </Select>
          <Input placeholder="Résumé (ex. Réponse de la DRH, entretien le 20/11)" value={summary} onChange={(e) => setSummary(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()} />
          <Button onClick={add}>Ajouter</Button>
        </div>
        <ul className="divide-y text-sm">
          {activities.map((a) => (
            <li key={a.id} className="flex gap-3 py-2">
              <span className="w-28 shrink-0 text-xs text-muted-foreground">{fmtDate(a.occurred_at, true)}</span>
              <span className="w-28 shrink-0 text-xs font-medium">{LABELS[a.type] || a.type}</span>
              <span className="min-w-0 flex-1">{a.summary}</span>
            </li>
          ))}
          {!activities.length && <li className="py-2 text-xs text-muted-foreground">Aucun échange enregistré.</li>}
        </ul>
      </CardContent>
    </Card>
  );
}
