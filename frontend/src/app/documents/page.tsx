"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { Download, Trash2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, Doc, download, fetcher, fmtDate, PROFILE_LABELS } from "@/lib/api";
import { PageHeader, Spin, useAction } from "@/components/shared";

export default function DocumentsPage() {
  const { data: docs, mutate } = useSWR<Doc[]>("/api/documents", fetcher);
  const { data: cats } = useSWR<Record<string, string>>("/api/documents/categories", fetcher);
  const [f, setF] = useState({ category: "cv_fr", language: "fr", profile_key: "shalom", title: "" });
  const fileRef = useRef<HTMLInputElement>(null);
  const { busy, run } = useAction();

  async function upload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    Object.entries(f).forEach(([k, v]) => fd.append(k, k === "profile_key" && v === "common" ? "" : v));
    await run("up", async () => {
      const r = await fetch(`/api/documents`, { method: "POST", body: fd });
      if (!r.ok) throw new Error((await r.json()).detail);
    }, "Document ajouté");
    if (fileRef.current) fileRef.current.value = "";
    setF({ ...f, title: "" });
    mutate();
  }

  const grouped = Object.entries(cats || {}).map(([k, label]) => ({ k, label, items: (docs || []).filter((d) => d.category === k) }));

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Bibliothèque documentaire" subtitle="CV, portfolio, plaquette, présentation, certificats. L'application recommande les pièces pertinentes ; vous validez chaque pièce jointe." />
      <Card className="mb-6">
        <CardHeader><CardTitle className="text-base">Importer un document</CardTitle></CardHeader>
        <CardContent className="grid gap-2 md:grid-cols-[1fr_170px_110px_160px_1fr_auto]">
          <Input ref={fileRef} type="file" accept=".pdf,.docx,.doc,.pptx,.jpg,.png,.txt,.md" />
          <Select value={f.category} onValueChange={(v) => setF({ ...f, category: v })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>{Object.entries(cats || {}).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={f.language} onValueChange={(v) => setF({ ...f, language: v })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="fr">FR</SelectItem><SelectItem value="en">EN</SelectItem></SelectContent>
          </Select>
          <Select value={f.profile_key} onValueChange={(v) => setF({ ...f, profile_key: v })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="shalom">Shalom Tehe</SelectItem><SelectItem value="kortex">KORTEX DIGITAL</SelectItem><SelectItem value="common">Commun</SelectItem></SelectContent>
          </Select>
          <Input placeholder="Titre (facultatif)" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
          <Button onClick={upload} disabled={busy === "up"}><Spin on={busy === "up"} /><Upload className="size-4" /> Ajouter</Button>
        </CardContent>
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        {grouped.map(({ k, label, items }) => (
          <Card key={k} className="gap-3">
            <CardHeader><CardTitle className="text-sm">{label} <span className="font-normal text-muted-foreground">({items.length})</span></CardTitle></CardHeader>
            <CardContent>
              {!items.length && <p className="text-xs text-muted-foreground">Aucun document.</p>}
              <ul className="divide-y">
                {items.map((d) => (
                  <li key={d.id} className="flex items-center gap-2 py-2 text-sm">
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium">{d.title}</div>
                      <div className="truncate text-xs text-muted-foreground">
                        {d.language.toUpperCase()} · {d.profile_key ? PROFILE_LABELS[d.profile_key] : "Commun"} · {(d.size_bytes / 1024).toFixed(0)} Ko · {fmtDate(d.created_at)}{d.has_text ? "" : " · texte non extrait"}
                      </div>
                      {d.notes && <div className="text-xs">{d.notes}</div>}
                    </div>
                    <Button size="icon" variant="ghost" onClick={() => run("dl", () => download(`/api/documents/${d.id}/download`, d.filename))}><Download className="size-4" /></Button>
                    <Button size="icon" variant="ghost" onClick={() => confirm(`Supprimer « ${d.title} » ?`) && run("del", () => api(`/api/documents/${d.id}`, { method: "DELETE" })).then(() => mutate())}><Trash2 className="size-4" /></Button>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
