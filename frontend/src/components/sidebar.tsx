"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  BarChart3, Briefcase, Building2, FileText, FolderOpen, Handshake, Kanban, Laptop, LogOut, Mail, Megaphone, Menu, Send, Settings, X, PenLine,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Dashboard", icon: BarChart3 },
  { href: "/entreprises", label: "Recherche d'entreprises", icon: Building2 },
  { href: "/offres", label: "Offres d'emploi", icon: Briefcase },
  { href: "/freelance", label: "Missions freelance", icon: Laptop },
  { href: "/b2b", label: "Opportunités B2B", icon: Handshake },
  { href: "/lettres", label: "Générateur de lettres", icon: PenLine },
  { href: "/emails", label: "Générateur d'emails", icon: Mail },
  { href: "/documents", label: "Bibliothèque documentaire", icon: FolderOpen },
  { href: "/candidatures", label: "Préparation des candidatures", icon: Send },
  { href: "/campagnes", label: "Campagnes (envoi par lots)", icon: Megaphone },
  { href: "/crm", label: "Suivi et CRM", icon: Kanban },
  { href: "/email", label: "Email et délivrabilité", icon: FileText },
  { href: "/parametres", label: "Paramètres", icon: Settings },
];

export function Sidebar() {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const nav = (
    <nav className="flex flex-col gap-0.5">
      {NAV.map(({ href, label, icon: Icon }, i) => {
        const active = href === "/" ? path === "/" : path.startsWith(href);
        return (
          <Link key={href} href={href} onClick={() => setOpen(false)}
            className={cn("flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
            <span className="w-4 text-[10px] tabular-nums opacity-60">{i + 1}</span>
            <Icon className="size-4 shrink-0" />
            <span className="truncate">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
  const brand = (
    <div className="px-3 pb-5">
      <div className="flex items-center gap-2">
        <div className="grid size-8 place-items-center rounded-md bg-primary font-serif text-lg font-bold text-primary-foreground">K</div>
        <div>
          <div className="text-sm font-semibold leading-tight">KORTEX Prospect</div>
          <div className="text-[11px] text-muted-foreground">Shalom Tehe · KORTEX DIGITAL</div>
        </div>
      </div>
    </div>
  );
  const footer = (
    <div className="mt-auto space-y-3 px-3 pt-6">
      <p className="text-[11px] leading-snug text-muted-foreground">
        Rien ne part sans votre validation : brouillons individuels, ou lots relus puis envoyés à rythme limité.
      </p>
      <button className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground"
        onClick={() => fetch("/api/auth/logout", { method: "POST" }).then(() => (location.href = "/login"))}>
        <LogOut className="size-3.5" /> Se déconnecter
      </button>
    </div>
  );
  return (
    <>
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r bg-background py-5 px-2 md:flex">
        {brand}
        {nav}
        {footer}
      </aside>
      <button className="fixed left-3 top-3 z-40 rounded-md border bg-background p-2 md:hidden" onClick={() => setOpen(true)} aria-label="Menu">
        <Menu className="size-5" />
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div className="flex w-72 flex-col overflow-y-auto bg-background px-2 py-5 shadow-xl">
            <button className="mb-3 ml-auto mr-2" onClick={() => setOpen(false)} aria-label="Fermer"><X className="size-5" /></button>
            {brand}
            {nav}
            {footer}
          </div>
          <div className="flex-1 bg-black/40" onClick={() => setOpen(false)} />
        </div>
      )}
    </>
  );
}
