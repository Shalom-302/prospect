"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { FileDown, Save, Sparkles, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, download, DOC_TYPE_LABELS, fetcher, fmtDate, Generated, PROFILE_LABELS } from "@/lib/api";
import { Spin, useAction } from "@/components/shared";

type Props = {
  opportunityId?: number | null;
  companyId?: number | null;
  defaultProfile: "shalom" | "kortex";
  defaultLanguage?: string;
  types?: Generated["doc_type"][];
  onChange?: () => void;
};

export function GeneratorPanel({ opportunityId, companyId, defaultProfile, defaultLanguage = "fr", types, onChange }: Props) {
  const allowed = types || (defaultProfile === "kortex" ? ["b2b_proposal", "email"] : ["cover_letter", "email"]);
  const [docType, setDocType] = useState<string>(allowed[0]);
  const [profile, setProfile] = useState<string>(defaultProfile);
  const [language, setLanguage] = useState(defaultLanguage);
  const [recipient, setRecipient] = useState("");
  const [instructions, setInstructions] = useState("");
  const qs = opportunityId ? `opportunity_id=${opportunityId}` : `company_id=${companyId}`;
  const { data: docs, mutate } = useSWR<Generated[]>(opportunityId || companyId ? `/api/generated?${qs}` : null, fetcher);
  const { busy, run } = useAction();

  useEffect(() => setLanguage(defaultLanguage), [defaultLanguage]);

  async function generate() {
    const lastLetter = docs?.find((d) => d.doc_type !== "email");
    const r = await run("gen", () => api("/api/generated", {
      method: "POST",
      json: { doc_type: docType, profile_key: profile, opportunity_id: opportunityId || null, company_id: opportunityId ? null : companyId,
              language, recipient_name: recipient, instructions, letter_id: docType === "email" ? lastLetter?.id ?? null : null },
    }), "Document généré — relisez-le avant usage");
    if (r) { mutate(); onChange?.(); }
  }

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Sparkles className="size-4" /> Lettres et emails</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-3">
          <Select value={docType} onValueChange={setDocType}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>{allowed.map((t) => <SelectItem key={t} value={t}>{DOC_TYPE_LABELS[t]}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={profile} onValueChange={setProfile}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>{Object.entries(PROFILE_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="fr">Français</SelectItem><SelectItem value="en">English</SelectItem></SelectContent>
          </Select>
        </div>
        <Input placeholder="Nom du destinataire (facultatif, ex. Mme Koné, DRH)" value={recipient} onChange={(e) => setRecipient(e.target.value)} />
        <Textarea rows={2} placeholder="Consignes (facultatif) : ex. insister sur RAG et Shaapi, ton plus direct…" value={instructions} onChange={(e) => setInstructions(e.target.value)} />
        <Button onClick={generate} disabled={busy === "gen"}><Spin on={busy === "gen"} /> Générer</Button>
        <div className="space-y-4">
          {docs?.map((d) => <DocEditor key={d.id} doc={d} onChange={() => { mutate(); onChange?.(); }} />)}
        </div>
      </CardContent>
    </Card>
  );
}

export function DocEditor({ doc, onChange }: { doc: Generated; onChange: () => void }) {
  const [subject, setSubject] = useState(doc.subject);
  const [content, setContent] = useState(doc.content);
  const dirty = subject !== doc.subject || content !== doc.content;
  const { busy, run } = useAction();
  return (
    <div className="rounded-lg border bg-background p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">{DOC_TYPE_LABELS[doc.doc_type]}</span>
        <span>· {doc.language.toUpperCase()} · {PROFILE_LABELS[doc.profile_key]} · {fmtDate(doc.updated_at, true)}{doc.edited ? " · modifié" : ""}</span>
      </div>
      <Label className="text-xs">Objet</Label>
      <Input className="mb-2" value={subject} onChange={(e) => setSubject(e.target.value)} />
      <Textarea rows={14} className="font-serif text-[13px] leading-relaxed" value={content} onChange={(e) => setContent(e.target.value)} />
      {content.includes("[À COMPLÉTER]") && <p className="mt-1 text-xs">⚠ Des champs [À COMPLÉTER] restent à remplir.</p>}
      <div className="mt-2 flex flex-wrap gap-2">
        <Button size="sm" variant={dirty ? "default" : "outline"} disabled={!dirty || busy === "save"}
          onClick={() => run("save", () => api(`/api/generated/${doc.id}`, { method: "PUT", json: { subject, content } }), "Enregistré").then(onChange)}>
          <Save className="size-3.5" /> Enregistrer
        </Button>
        {doc.doc_type !== "email" && (
          <>
            <Button size="sm" variant="outline" onClick={() => run("pdf", () => download(`/api/generated/${doc.id}/export?format=pdf`))}><FileDown className="size-3.5" /> PDF</Button>
            <Button size="sm" variant="outline" onClick={() => run("docx", () => download(`/api/generated/${doc.id}/export?format=docx`))}><FileDown className="size-3.5" /> DOCX</Button>
          </>
        )}
        <Button size="sm" variant="ghost" className="ml-auto" onClick={() => confirm("Supprimer ce document ?") && run("del", () => api(`/api/generated/${doc.id}`, { method: "DELETE" })).then(onChange)}>
          <Trash2 className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}
