"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Sidebar } from "@/components/sidebar";

const PUBLIC = ["/login", "/u/"];

/** Affiche le menu et vérifie la session (connexion WhatsApp) ; les pages publiques s'affichent seules. */
export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const isPublic = PUBLIC.some((p) => path.startsWith(p));
  const [ok, setOk] = useState(isPublic);

  useEffect(() => {
    if (isPublic) return;
    fetch("/api/auth/me").then((r) => (r.ok ? setOk(true) : router.replace("/login"))).catch(() => setOk(true));
  }, [isPublic, router]);

  if (isPublic) return <main className="min-h-screen">{children}</main>;
  if (!ok) return null;
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 min-w-0 px-4 py-6 md:px-8 lg:px-10 pt-16 md:pt-6">{children}</main>
    </div>
  );
}
