"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, Company, fetcher, fmtDate } from "@/lib/api";
import { Empty, PageHeader, ScoreBadge, Spin, StatusBadge, useAction } from "@/components/shared";

const SECTORS = ["Banque", "Assurance", "Microfinance", "Santé", "Énergie", "Télécoms", "Éducation", "Industrie", "Logistique et transport",
  "Distribution et commerce", "Agro-industrie", "Mines", "BTP et immobilier", "Hôtellerie", "Sport", "ONG", "Administration"];

export default function CompaniesPage() {
  const [f, setF] = useState({ q: "", country: "", city: "", sector: "", has_email: false });
  const qs = useMemo(() => {
    const p = new URLSearchParams({ limit: "300" });
    Object.entries(f).forEach(([k, v]) => v && p.set(k, String(v)));
    return p.toString();
  }, [f]);
  const { data, mutate } = useSWR<{ total: number; items: Company[] }>(`/api/companies?${qs}`, fetcher);

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title="Recherche d'entreprises" subtitle="Découverte d'entreprises et de leurs coordonnées publiques. Chaque contact garde sa source et son niveau de confiance.">
        <AddCompany onDone={() => mutate()} />
      </PageHeader>
      <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <div className="space-y-6">
          <CompanySearch onDone={() => mutate()} />
          <Sources />
        </div>
        <Card>
          <CardHeader className="gap-3">
            <CardTitle className="text-base">{data?.total ?? "…"} entreprise(s)</CardTitle>
            <div className="flex flex-wrap items-center gap-2">
              <Input className="h-8 w-48" placeholder="Nom, domaine…" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
              <Input className="h-8 w-32" placeholder="Pays" value={f.country} onChange={(e) => setF({ ...f, country: e.target.value })} />
              <Input className="h-8 w-32" placeholder="Ville" value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })} />
              <Input className="h-8 w-32" placeholder="Secteur" value={f.sector} onChange={(e) => setF({ ...f, sector: e.target.value })} />
              <label className="flex items-center gap-2 text-xs text-muted-foreground"><Switch checked={f.has_email} onCheckedChange={(v) => setF({ ...f, has_email: v })} /> Avec email</label>
            </div>
          </CardHeader>
          <CardContent>
            {data && !data.items.length ? <Empty>Aucune entreprise. Lancez une recherche web ou ajoutez-en une avec son site.</Empty> : (
              <Table>
                <TableHeader>
                  <TableRow><TableHead>Score</TableHead><TableHead>Entreprise</TableHead><TableHead className="hidden md:table-cell">Secteur · lieu</TableHead><TableHead>Emails</TableHead><TableHead className="hidden lg:table-cell">Statut</TableHead></TableRow>
                </TableHeader>
                <TableBody>
                  {data?.items.map((c) => (
                    <TableRow key={c.id} className="cursor-pointer">
                      <TableCell><ScoreBadge score={c.score} method={c.score_method} /></TableCell>
                      <TableCell>
                        <Link href={`/entreprises/${c.id}`} className="font-medium hover:underline">{c.name}</Link>
                        <div className="text-xs text-muted-foreground">{c.domain || "site inconnu"} · {c.source_name} · {fmtDate(c.collected_at)}</div>
                      </TableCell>
                      <TableCell className="hidden text-sm md:table-cell">{[c.sector, c.city, c.country].filter(Boolean).join(" · ")}</TableCell>
                      <TableCell className="text-sm tabular-nums">{c.emails}{c.verified_emails ? <span className="text-xs text-muted-foreground"> ({c.verified_emails} site off.)</span> : null}</TableCell>
                      <TableCell className="hidden lg:table-cell"><StatusBadge status={c.status} /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function CompanySearch({ onDone }: { onDone: () => void }) {
  const { data: meta } = useSWR("/api/search/meta", fetcher);
  const [p, setP] = useState({ sector: "Banque", keywords: "transformation digitale", country: "Côte d'Ivoire", city: "Abidjan", limit: 15 });
  const { busy, run } = useAction();
  const tavily = meta?.connectors?.find((c: any) => c.name === "tavily");
  async function go() {
    const r = await run("s", () => api("/api/search/companies", { method: "POST", json: { ...p, keywords: p.keywords.split(",").map((s) => s.trim()).filter(Boolean) } }));
    if (r) {
      r.run.status === "done" ? toast.success(`${r.run.created} nouvelle(s) entreprise(s), ${r.run.duplicates} déjà connue(s)`) : toast.error(r.run.message);
      onDone();
    }
  }
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Search className="size-4" /> Découvrir des entreprises</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1.5"><Label>Secteur</Label>
          <Input list="sectors" value={p.sector} onChange={(e) => setP({ ...p, sector: e.target.value })} />
          <datalist id="sectors">{SECTORS.map((s) => <option key={s} value={s} />)}</datalist>
        </div>
        <div className="space-y-1.5"><Label>Mots-clés</Label><Input value={p.keywords} onChange={(e) => setP({ ...p, keywords: e.target.value })} /></div>
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1.5"><Label>Pays</Label><Input value={p.country} onChange={(e) => setP({ ...p, country: e.target.value })} /></div>
          <div className="space-y-1.5"><Label>Ville</Label>
            <Input list="ci-cities" value={p.city} onChange={(e) => setP({ ...p, city: e.target.value })} />
            <datalist id="ci-cities">{(meta?.geo?.cote_ivoire?.places || []).map((x: string) => <option key={x} value={x} />)}</datalist>
          </div>
        </div>
        <Button className="w-full" onClick={go} disabled={busy === "s" || !tavily?.available}><Spin on={busy === "s"} /> Rechercher</Button>
        {!tavily?.available && <p className="text-xs text-muted-foreground">Ajoutez TAVILY_API_KEY dans .env pour activer la recherche web. En attendant, ajoutez les entreprises manuellement avec leur site.</p>}
        <p className="text-[11px] text-muted-foreground">Les entreprises trouvées sont « à qualifier ». Ouvrez une fiche puis « Scanner le site » pour collecter les coordonnées publiées.</p>
      </CardContent>
    </Card>
  );
}

function Sources() {
  const { data: meta } = useSWR("/api/search/meta", fetcher);
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Annuaires à consulter</CardTitle></CardHeader>
      <CardContent className="space-y-1.5 text-sm">
        {meta?.company_sources?.map((s: any) => (
          <a key={s.name} href={s.url} target="_blank" rel="noreferrer" className="block hover:underline">{s.name}{s.note && <span className="block text-[11px] text-muted-foreground">{s.note}</span>}</a>
        ))}
      </CardContent>
    </Card>
  );
}

function AddCompany({ onDone }: { onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", website: "", sector: "", country: "Côte d'Ivoire", city: "Abidjan", description: "", source_url: "" });
  const { busy, run } = useAction();
  async function submit() {
    const r = await run("add", () => api("/api/companies", { method: "POST", json: { ...form, website: form.website || null } }));
    if (r) {
      toast.success(r.created ? `Ajoutée${r.scan ? ` · ${r.scan.contacts_added} contact(s) trouvé(s) sur le site` : ""}` : "Entreprise déjà présente");
      if (r.scan?.blocked?.length) toast.message("Pages non accessibles : " + r.scan.blocked.slice(0, 2).join(" ; "));
      setOpen(false);
      onDone();
    }
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button><Plus className="size-4" /> Ajouter une entreprise</Button></DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Ajouter une entreprise</DialogTitle>
          <DialogDescription>Avec son site officiel, l&apos;application lit les pages publiques (accueil, contact, carrières) autorisées par robots.txt.</DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Input placeholder="Nom officiel *" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <Input placeholder="Site web (ex. www.entreprise.ci)" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} />
          <div className="grid grid-cols-3 gap-2">
            <Input placeholder="Secteur" list="sectors2" value={form.sector} onChange={(e) => setForm({ ...form, sector: e.target.value })} />
            <Input placeholder="Pays" value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} />
            <Input placeholder="Ville" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
            <datalist id="sectors2">{SECTORS.map((s) => <option key={s} value={s} />)}</datalist>
          </div>
          <Input placeholder="Source (URL où vous l'avez trouvée)" value={form.source_url} onChange={(e) => setForm({ ...form, source_url: e.target.value })} />
          <Textarea placeholder="Description / notes" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </div>
        <DialogFooter><Button onClick={submit} disabled={!form.name || busy === "add"}><Spin on={busy === "add"} /> Ajouter</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
