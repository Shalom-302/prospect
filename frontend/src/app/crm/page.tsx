"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, fetcher, fmtDate, KIND_LABELS } from "@/lib/api";
import { PageHeader, ScoreBadge, useAction } from "@/components/shared";

type Col = { key: string; label: string; items: any[] };

export default function CrmPage() {
  const [profile, setProfile] = useState("all");
  const { data, mutate } = useSWR<Col[]>(`/api/pipeline${profile !== "all" ? `?profile_key=${profile}` : ""}`, fetcher);
  const { run } = useAction();
  const [drag, setDrag] = useState<any>(null);

  async function move(item: any, status: string) {
    const path = item.type === "company" ? `/api/companies/${item.id}` : `/api/opportunities/${item.id}`;
    await run("mv", () => api(path, { method: "PATCH", json: { status } }));
    mutate();
  }

  return (
    <div>
      <PageHeader title="Suivi et CRM" subtitle="Pipeline des opportunités et prospects. Glissez une carte pour changer son statut (les « Découverte » non traitées sont masquées).">
        <Tabs value={profile} onValueChange={setProfile}>
          <TabsList><TabsTrigger value="all">Tous</TabsTrigger><TabsTrigger value="shalom">Shalom</TabsTrigger><TabsTrigger value="kortex">KORTEX</TabsTrigger></TabsList>
        </Tabs>
      </PageHeader>
      <div className="flex gap-3 overflow-x-auto pb-4">
        {data?.filter((c) => c.key !== "decouverte").map((col) => (
          <div key={col.key} className="flex w-64 shrink-0 flex-col rounded-lg bg-muted/60 p-2"
            onDragOver={(e) => e.preventDefault()} onDrop={() => drag && drag.status !== col.key && move(drag, col.key)}>
            <div className="mb-2 flex items-center justify-between px-1 text-xs font-medium">
              <span>{col.label}</span><span className="tabular-nums text-muted-foreground">{col.items.length}</span>
            </div>
            <div className="flex max-h-[70vh] flex-col gap-2 overflow-y-auto">
              {col.items.map((it) => (
                <Link key={it.type + it.id} href={it.type === "company" ? `/entreprises/${it.id}` : `/opportunites/${it.id}`}
                  draggable onDragStart={() => setDrag({ ...it, status: col.key })}
                  className="rounded-md border bg-background p-2 text-sm shadow-xs hover:border-foreground/30">
                  <div className="flex items-start gap-2">
                    <ScoreBadge score={it.score} />
                    <div className="min-w-0 flex-1">
                      <div className="line-clamp-2 font-medium leading-snug">{it.title}</div>
                      <div className="truncate text-xs text-muted-foreground">{it.subtitle}</div>
                    </div>
                  </div>
                  <div className="mt-1.5 flex justify-between text-[10px] text-muted-foreground">
                    <span>{it.type === "company" ? "Entreprise" : KIND_LABELS[it.kind]} · {it.profile_key === "kortex" ? "KORTEX" : "Shalom"}</span>
                    {it.next_action_date && <span>⏰ {fmtDate(it.next_action_date)}</span>}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
