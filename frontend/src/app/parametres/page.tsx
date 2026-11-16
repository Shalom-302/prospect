"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { CheckCircle2, CircleAlert, Play, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, fetcher, fmtDate } from "@/lib/api";
import { PageHeader, Spin, useAction } from "@/components/shared";

export default function SettingsPage() {
  const { data: st } = useSWR<any>("/api/settings/status", fetcher);
  const { busy, run } = useAction();
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="Paramètres" subtitle="Les clés API se configurent dans le fichier .env du serveur — elles ne transitent jamais par le navigateur." />
      <div className="mb-6 grid gap-4 md:grid-cols-3">
        <Status ok={st?.llm?.configured} title="LLM (compatible OpenAI)" detail={st?.llm?.configured ? `${st.llm.model} · ${st.llm.base_url}` : "LLM_BASE_URL, LLM_API_KEY, LLM_MODEL"}>
          {st?.llm?.configured && <Button size="sm" variant="outline" disabled={busy === "t"} onClick={() => run("t", () => api("/api/settings/llm-test", { method: "POST" }), (r: any) => `Réponse du modèle : ${r.reply}`)}><Spin on={busy === "t"} /> Tester</Button>}
        </Status>
        <Status ok={st?.tavily?.configured} title="Recherche web Tavily" detail={st?.tavily?.configured ? "Clé configurée" : "TAVILY_API_KEY"} />
        <Status ok={st?.zoho?.connected} title="Zoho Mail" detail={st?.zoho?.connected ? st.zoho.email : st?.zoho?.configured ? "Configuré, non connecté" : "ZOHO_CLIENT_ID / SECRET"} />
      </div>
      <Tabs defaultValue="profiles">
        <TabsList><TabsTrigger value="profiles">Profils</TabsTrigger><TabsTrigger value="saved">Recherches programmées</TabsTrigger><TabsTrigger value="rules">Règles</TabsTrigger></TabsList>
        <TabsContent value="profiles"><Profiles /></TabsContent>
        <TabsContent value="saved"><Saved /></TabsContent>
        <TabsContent value="rules">
          <Card><CardContent className="pt-6"><ul className="list-disc space-y-1 pl-5 text-sm">{st?.rules?.map((r: string) => <li key={r}>{r}</li>)}</ul></CardContent></Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Status({ ok, title, detail, children }: { ok?: boolean; title: string; detail: string; children?: React.ReactNode }) {
  return (
    <Card className="gap-2 py-4">
      <CardContent className="space-y-2 px-4">
        <div className="flex items-center gap-2 text-sm font-medium">{ok ? <CheckCircle2 className="size-4" /> : <CircleAlert className="size-4 text-muted-foreground" />}{title}</div>
        <div className="truncate text-xs text-muted-foreground">{detail}</div>
        {children}
      </CardContent>
    </Card>
  );
}

function Profiles() {
  const { data, mutate } = useSWR<any[]>("/api/profiles", fetcher);
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {data?.map((p) => <ProfileEditor key={p.key} profile={p} onSaved={() => mutate()} />)}
    </div>
  );
}

function ProfileEditor({ profile, onSaved }: { profile: any; onSaved: () => void }) {
  const [text, setText] = useState("");
  useEffect(() => setText(JSON.stringify(profile.data, null, 2)), [profile]);
  const { busy, run } = useAction();
  async function save() {
    let data;
    try { data = JSON.parse(text); } catch (e: any) { toast.error("JSON invalide : " + e.message); return; }
    await run("s", () => api(`/api/profiles/${profile.key}`, { method: "PUT", json: { data } }), "Profil enregistré");
    onSaved();
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{profile.display_name}</CardTitle>
        <p className="text-xs text-muted-foreground">Source de vérité utilisée par l&apos;IA. N&apos;y mettez que des informations exactes : tout ce qui est ici peut apparaître dans une lettre.</p>
      </CardHeader>
      <CardContent className="space-y-2">
        <Textarea rows={22} className="font-mono text-xs" value={text} onChange={(e) => setText(e.target.value)} />
        <Button onClick={save} disabled={busy === "s"}><Spin on={busy === "s"} /> Enregistrer</Button>
      </CardContent>
    </Card>
  );
}

function Saved() {
  const { data, mutate } = useSWR<any[]>("/api/search/saved", fetcher);
  const { busy, run } = useAction();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Recherches enregistrées</CardTitle>
        <p className="text-xs text-muted-foreground">Les recherches « chaque matin » s&apos;exécutent à 7 h (Abidjan) via le worker Celery. Enregistrez-en depuis les pages Offres / Freelance / B2B.</p>
      </CardHeader>
      <CardContent>
        <ul className="divide-y">
          {data?.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
              <div className="min-w-0 flex-1">
                <div className="font-medium">{s.name}</div>
                <div className="text-xs text-muted-foreground">{(s.params.keywords || []).join(", ")} · {(s.params.connectors || []).join(", ")} · dernière exécution {fmtDate(s.last_run_at, true)}</div>
              </div>
              <label className="flex items-center gap-2 text-xs">chaque matin
                <Switch checked={s.scheduled} onCheckedChange={(v) => run("p", () => api(`/api/search/saved/${s.id}`, { method: "PATCH", json: { scheduled: v } })).then(() => mutate())} />
              </label>
              <Button size="sm" variant="outline" disabled={busy === `r${s.id}`} onClick={() => run(`r${s.id}`, () => api(`/api/search/saved/${s.id}/run`, { method: "POST" }), (r: any) => r.runs.map((x: any) => `${x.connector}: +${x.created}`).join(" · ")).then(() => mutate())}>
                <Spin on={busy === `r${s.id}`} /><Play className="size-3.5" /> Lancer
              </Button>
              <Button size="icon" variant="ghost" onClick={() => run("d", () => api(`/api/search/saved/${s.id}`, { method: "DELETE" })).then(() => mutate())}><Trash2 className="size-4" /></Button>
            </li>
          ))}
          {!data?.length && <li className="py-2 text-sm text-muted-foreground">Aucune recherche enregistrée.</li>}
        </ul>
      </CardContent>
    </Card>
  );
}
