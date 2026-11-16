"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import useSWR from "swr";
import { ClipboardPaste, ExternalLink, Globe, Save, Search, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api, fetcher, fmtDate, Opportunity, STATUS_LABELS } from "@/lib/api";
import { Empty, PageHeader, ScoreBadge, Spin, StatusBadge, useAction } from "@/components/shared";

const DEFAULT_KEYWORDS: Record<string, string> = {
  job: "python, fastapi, backend, llm, ai engineer",
  freelance: "fastapi, python backend, llm, ai agent, rag",
  b2b: "développement logiciel, intelligence artificielle, automatisation, application métier",
};

type Props = { kind: "job" | "freelance" | "b2b"; title: string; subtitle: string; children?: React.ReactNode };

export function OpportunityExplorer({ kind, title, subtitle, children }: Props) {
  const [filters, setFilters] = useState({ q: "", min_score: "", status: "", verified_only: false, sort: "score" });
  const qs = useMemo(() => {
    const p = new URLSearchParams({ kind, sort: filters.sort, limit: "200" });
    if (filters.q) p.set("q", filters.q);
    if (filters.min_score) p.set("min_score", filters.min_score);
    if (filters.status) p.set("status", filters.status);
    if (filters.verified_only) p.set("verified_only", "true");
    return p.toString();
  }, [kind, filters]);
  const { data, mutate, isLoading } = useSWR<{ total: number; items: Opportunity[] }>(`/api/opportunities?${qs}`, fetcher);

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title={title} subtitle={subtitle}>
        <ImportDialog kind={kind} onDone={() => mutate()} />
      </PageHeader>
      <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <div className="space-y-6">
          <SearchPanel kind={kind} onDone={() => mutate()} />
          {children}
          <PlatformsPanel kind={kind} onDone={() => mutate()} />
        </div>
        <Card className="min-w-0">
          <CardHeader className="gap-3">
            <CardTitle className="text-base">{data?.total ?? "…"} résultat(s)</CardTitle>
            <div className="flex flex-wrap items-center gap-2">
              <Input placeholder="Filtrer (titre, entreprise, lieu…)" className="h-8 w-56" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} />
              <Select value={filters.min_score || "0"} onValueChange={(v) => setFilters({ ...filters, min_score: v === "0" ? "" : v })}>
                <SelectTrigger className="h-8 w-36"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="0">Tous scores</SelectItem>
                  <SelectItem value="50">Score ≥ 50</SelectItem>
                  <SelectItem value="70">Score ≥ 70</SelectItem>
                  <SelectItem value="85">Score ≥ 85</SelectItem>
                </SelectContent>
              </Select>
              <Select value={filters.status || "all"} onValueChange={(v) => setFilters({ ...filters, status: v === "all" ? "" : v })}>
                <SelectTrigger className="h-8 w-44"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tous statuts actifs</SelectItem>
                  {Object.entries(STATUS_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={filters.sort} onValueChange={(v) => setFilters({ ...filters, sort: v })}>
                <SelectTrigger className="h-8 w-40"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="score">Tri : pertinence</SelectItem>
                  <SelectItem value="date">Tri : publication</SelectItem>
                  <SelectItem value="collected">Tri : collecte</SelectItem>
                </SelectContent>
              </Select>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <Switch checked={filters.verified_only} onCheckedChange={(v) => setFilters({ ...filters, verified_only: v })} /> Annonces complètes uniquement
              </label>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading && <p className="text-sm text-muted-foreground">Chargement…</p>}
            {data && !data.items.length && <Empty>Aucun résultat. Lancez une recherche ou importez une annonce.</Empty>}
            <ul className="divide-y">
              {data?.items.map((o) => (
                <li key={o.id}>
                  <Link href={`/opportunites/${o.id}`} className="flex gap-3 py-3 hover:bg-muted/60 -mx-2 px-2 rounded-md">
                    <div className="pt-0.5"><ScoreBadge score={o.score} method={o.score_method} /></div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{o.title}</span>
                        {o.needs_verification && <span className="inline-flex items-center gap-1 rounded border border-dashed px-1.5 text-[10px] text-muted-foreground"><ShieldAlert className="size-3" />à vérifier</span>}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {[o.company_name || "Entreprise non précisée", o.location, o.remote ? "Remote" : null, o.contract_type, o.salary && `${o.salary} ${o.currency}`].filter(Boolean).join(" · ")}
                      </div>
                      <div className="mt-1 line-clamp-2 text-xs text-muted-foreground/80">{o.excerpt}</div>
                      <div className="mt-1 text-[11px] text-muted-foreground">
                        {o.source} · publiée {fmtDate(o.published_at)} · collectée {fmtDate(o.collected_at)}{o.deadline && ` · limite ${fmtDate(o.deadline)}`}
                      </div>
                    </div>
                    <div className="hidden sm:block"><StatusBadge status={o.status} /></div>
                  </Link>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function SearchPanel({ kind, onDone }: { kind: string; onDone: () => void }) {
  const { data: meta } = useSWR("/api/search/meta", fetcher);
  const [keywords, setKeywords] = useState(DEFAULT_KEYWORDS[kind]);
  const [country, setCountry] = useState(kind === "b2b" ? "Côte d'Ivoire" : "");
  const [city, setCity] = useState("");
  const [sources, setSources] = useState<string[]>(kind === "b2b" ? ["tavily"] : ["remotive", "remoteok", "weworkremotely"]);
  const [saveName, setSaveName] = useState("");
  const [scheduled, setScheduled] = useState(true);
  const { busy, run } = useAction();

  const body = () => ({
    keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
    country, city, kind, connectors: sources, profile_key: kind === "b2b" ? "kortex" : "shalom", limit: 30,
  });

  async function search() {
    const r = await run("search", () => api("/api/search/opportunities", { method: "POST", json: body() }));
    if (!r) return;
    for (const x of r.runs) {
      if (x.status === "done") toast.success(`${x.connector} : ${x.created} nouvelle(s), ${x.duplicates} doublon(s). ${x.message}`);
      else toast.error(`${x.connector} : ${x.message}`);
    }
    onDone();
  }

  async function save() {
    await run("save", () => api("/api/search/saved", { method: "POST", json: { name: saveName || `${kind} — ${keywords.slice(0, 40)}`, target: "opportunities", params: body(), scheduled } }), "Recherche enregistrée");
    setSaveName("");
  }

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Search className="size-4" /> Nouvelle recherche</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1.5">
          <Label>Mots-clés (séparés par des virgules)</Label>
          <Input value={keywords} onChange={(e) => setKeywords(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1.5">
            <Label>Pays</Label>
            <Input value={country} onChange={(e) => setCountry(e.target.value)} placeholder="Tous / Remote" list="geo-countries" />
          </div>
          <div className="space-y-1.5">
            <Label>Ville</Label>
            <Input value={city} onChange={(e) => setCity(e.target.value)} placeholder="ex. Abidjan" list="geo-cities" />
          </div>
          <datalist id="geo-countries">
            {["Côte d'Ivoire", ...(meta?.geo?.afrique?.places || []), ...(meta?.geo?.international?.places || [])].map((p: string) => <option key={p} value={p} />)}
          </datalist>
          <datalist id="geo-cities">{(meta?.geo?.cote_ivoire?.places || []).map((p: string) => <option key={p} value={p} />)}</datalist>
        </div>
        <div className="space-y-1.5">
          <Label>Sources</Label>
          <div className="space-y-1.5">
            {meta?.connectors?.map((c: any) => (
              <label key={c.name} className="flex items-center gap-2 text-sm">
                <Checkbox checked={sources.includes(c.name)} disabled={!c.available}
                  onCheckedChange={(v) => setSources(v ? [...sources, c.name] : sources.filter((s) => s !== c.name))} />
                <span className={c.available ? "" : "text-muted-foreground"}>{c.label}</span>
                {!c.available && <span className="text-[11px] text-muted-foreground">({c.requires} manquante)</span>}
              </label>
            ))}
          </div>
          <p className="text-[11px] text-muted-foreground">Les API Remotive / Remote OK / WWR listent surtout du remote international. Pour la Côte d&apos;Ivoire et l&apos;Afrique, utilisez la recherche web et les plateformes ci-dessous.</p>
        </div>
        <Button className="w-full" onClick={search} disabled={busy === "search" || !sources.length}><Spin on={busy === "search"} /> Rechercher</Button>
        <div className="flex items-center gap-2 border-t pt-3">
          <Input className="h-8" placeholder="Nom de la recherche" value={saveName} onChange={(e) => setSaveName(e.target.value)} />
          <label className="flex shrink-0 items-center gap-1 text-[11px] text-muted-foreground"><Checkbox checked={scheduled} onCheckedChange={(v) => setScheduled(!!v)} /> chaque matin</label>
          <Button size="sm" variant="outline" onClick={save} disabled={busy === "save"}><Save className="size-3.5" /></Button>
        </div>
      </CardContent>
    </Card>
  );
}

function PlatformsPanel({ kind, onDone }: { kind: string; onDone: () => void }) {
  const [q, setQ] = useState(kind === "freelance" ? "fastapi python" : "python backend developer");
  const { data } = useSWR(`/api/search/platforms?q=${encodeURIComponent(q)}`, fetcher);
  const { busy, run } = useAction();
  const relevant = (data || []).filter((p: any) => p.kinds.includes(kind === "b2b" ? "job" : kind) && p.access !== "api" && p.access !== "rss");
  const regions: Record<string, string> = { cote_ivoire: "Côte d'Ivoire", afrique: "Afrique", international: "International" };

  async function siteSearch(domain: string) {
    const r = await run(domain, () => api("/api/search/opportunities", { method: "POST", json: { keywords: q.split(" "), kind, connectors: ["tavily"], include_domains: [domain], limit: 15 } }));
    if (r) {
      const x = r.runs[0];
      x.status === "done" ? toast.success(`${domain} : ${x.created} nouveau(x) résultat(s) à vérifier`) : toast.error(x.message);
      onDone();
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base"><Globe className="size-4" /> Plateformes</CardTitle>
        <p className="text-xs text-muted-foreground">Ces sites interdisent ou bloquent la collecte automatique. Ouvrez la recherche vous-même, ou cherchez via l&apos;index web (Tavily), puis importez l&apos;annonce.</p>
        <Input className="mt-2 h-8" value={q} onChange={(e) => setQ(e.target.value)} />
      </CardHeader>
      <CardContent className="space-y-4">
        {Object.entries(regions).map(([rk, rl]) => {
          const list = relevant.filter((p: any) => p.region === rk);
          if (!list.length) return null;
          return (
            <div key={rk}>
              <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{rl}</div>
              <ul className="space-y-1">
                {list.map((p: any) => (
                  <li key={p.name} className="flex items-center gap-2 text-sm">
                    <a href={p.search_link} target="_blank" rel="noreferrer" className="flex min-w-0 flex-1 items-center gap-1.5 hover:underline" title={p.check}>
                      <ExternalLink className="size-3 shrink-0" /> <span className="truncate">{p.name}</span>
                    </a>
                    {p.access === "profile" ? (
                      <span className="text-[10px] text-muted-foreground">profil</span>
                    ) : (
                      <Button size="sm" variant="ghost" className="h-6 px-2 text-[11px]" disabled={busy === p.domain} onClick={() => siteSearch(p.domain)}>
                        <Spin on={busy === p.domain} /> via web
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export function ImportDialog({ kind, onDone }: { kind: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ url: "", text: "", title: "", company_name: "" });
  const { busy, run } = useAction();
  async function submit() {
    const r = await run("import", () => api("/api/opportunities/import", { method: "POST", json: { ...form, kind, profile_key: kind === "b2b" ? "kortex" : "shalom" } }));
    if (r) {
      toast.success(r.status === "duplicate" ? "Annonce déjà présente (doublon)" : "Annonce importée");
      setOpen(false);
      setForm({ url: "", text: "", title: "", company_name: "" });
      onDone();
    }
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button variant="outline"><ClipboardPaste className="size-4" /> Importer une annonce</Button></DialogTrigger>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Importer une annonce</DialogTitle>
          <DialogDescription>Copiez le texte d&apos;une annonce (LinkedIn, Indeed, Emploi.ci, Upwork…) ou collez l&apos;URL d&apos;une page publique. L&apos;IA en extrait les informations ; rien n&apos;est inventé.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Input placeholder="URL de l'annonce" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} />
          <div className="grid grid-cols-2 gap-2">
            <Input placeholder="Intitulé (si pas de LLM)" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <Input placeholder="Entreprise (si pas de LLM)" value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} />
          </div>
          <Textarea rows={12} placeholder="Texte complet de l'annonce" value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} />
        </div>
        <DialogFooter><Button onClick={submit} disabled={busy === "import" || (!form.text && !form.url)}><Spin on={busy === "import"} /> Importer</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
