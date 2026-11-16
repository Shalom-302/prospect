"use client";

import { useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, CircleHelp, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Analysis, CONFIDENCE_LABELS, STATUS_LABELS } from "@/lib/api";
import { cn } from "@/lib/utils";

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </div>
  );
}

export function ScoreBadge({ score, method }: { score: number | null | undefined; method?: string }) {
  if (score == null) return <span className="text-xs text-muted-foreground">—</span>;
  const tone = score >= 75 ? "bg-primary text-primary-foreground" : score >= 55 ? "bg-foreground/15 text-foreground" : "bg-muted text-muted-foreground";
  return (
    <span title={method === "llm" ? "Score IA" : "Score heuristique (règles)"}
      className={cn("inline-flex min-w-11 items-center justify-center gap-0.5 rounded-md px-1.5 py-0.5 text-xs font-semibold tabular-nums", tone)}>
      {Math.round(score)}
      {method === "llm" && <span className="text-[9px] font-normal opacity-70">IA</span>}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge variant="outline" className="font-normal">{STATUS_LABELS[status] || status}</Badge>;
}

export function StatusSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="h-8 w-56"><SelectValue /></SelectTrigger>
      <SelectContent>
        {Object.entries(STATUS_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}

export function ConfidenceBadge({ confidence }: { confidence: string }) {
  const Icon = confidence === "verified" ? CheckCircle2 : confidence === "estimated" ? AlertTriangle : CircleHelp;
  return (
    <span className={cn("inline-flex items-center gap-1 text-xs", confidence === "verified" ? "text-foreground" : "text-muted-foreground")}>
      <Icon className="size-3.5" />
      {CONFIDENCE_LABELS[confidence] || confidence}
    </span>
  );
}

export function ScoreBreakdown({ analysis }: { analysis: Analysis | null | undefined }) {
  if (!analysis) return <p className="text-sm text-muted-foreground">Pas encore qualifié.</p>;
  return (
    <div className="space-y-4">
      <div className="flex items-baseline gap-3">
        <span className="text-4xl font-semibold tabular-nums">{Math.round(analysis.total)}</span>
        <span className="text-sm text-muted-foreground">/ 100 · {analysis.method === "llm" ? `analyse IA (${analysis.model || "LLM"})` : "score heuristique"}</span>
      </div>
      {analysis.summary && <p className="text-sm">{analysis.summary}</p>}
      <div className="space-y-3">
        {Object.entries(analysis.criteria).map(([k, c]) => (
          <div key={k}>
            <div className="flex justify-between text-xs">
              <span className="font-medium">{c.label}</span>
              <span className="tabular-nums text-muted-foreground">{c.score} / {c.max}</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-foreground" style={{ width: `${(c.score / c.max) * 100}%` }} />
            </div>
            {c.reason && <p className="mt-1 text-xs text-muted-foreground">{c.reason}</p>}
          </div>
        ))}
      </div>
      {analysis.method === "llm" && (
        <dl className="grid gap-3 border-t pt-4 text-sm">
          {analysis.matched?.length ? <Item label="Compétences / services correspondants">{analysis.matched.join(" · ")}</Item> : null}
          <Item label="Profil recommandé">{analysis.recommended_profile === "kortex" ? "KORTEX DIGITAL" : "Shalom Tehe"}
            {" "}(pertinent Shalom : {analysis.relevant_shalom ? "oui" : "non"} · KORTEX : {analysis.relevant_kortex ? "oui" : "non"})</Item>
          {analysis.contact_to_target && <Item label="Interlocuteur à contacter">{analysis.contact_to_target}</Item>}
          {analysis.documents_to_attach?.length ? <Item label="Documents suggérés">{analysis.documents_to_attach.join(", ")}</Item> : null}
          {analysis.approach && <Item label="Approche recommandée">{analysis.approach}</Item>}
        </dl>
      )}
      {analysis.red_flags?.length ? (
        <div className="rounded-md border border-dashed p-3">
          <div className="mb-1 flex items-center gap-1.5 text-xs font-medium"><AlertTriangle className="size-3.5" /> Points de vigilance</div>
          <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">{analysis.red_flags.map((f, i) => <li key={i}>{f}</li>)}</ul>
        </div>
      ) : null}
    </div>
  );
}

function Item({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="rounded-lg border border-dashed bg-background p-10 text-center text-sm text-muted-foreground">{children}</div>;
}

/** Exécute une action asynchrone avec état de chargement et notification. */
export function useAction() {
  const [busy, setBusy] = useState<string | null>(null);
  async function run<T>(key: string, fn: () => Promise<T>, success?: string | ((r: T) => string)): Promise<T | undefined> {
    setBusy(key);
    try {
      const r = await fn();
      if (success) toast.success(typeof success === "function" ? success(r) : success);
      return r;
    } catch (e: any) {
      toast.error(e?.message || "Erreur");
      return undefined;
    } finally {
      setBusy(null);
    }
  }
  return { busy, run };
}

export function Spin({ on }: { on: boolean }) {
  return on ? <Loader2 className="size-4 animate-spin" /> : null;
}
