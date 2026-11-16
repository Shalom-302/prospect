"use client";

import { use, useEffect, useState } from "react";

/** Page publique de désinscription (lien présent dans chaque email de prospection). */
export default function Unsubscribe({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [email, setEmail] = useState<string | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "done" | "invalid">("loading");

  useEffect(() => {
    fetch(`/api/public/unsubscribe-info/${token}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => { setEmail(d.email); setState("ready"); })
      .catch(() => setState("invalid"));
  }, [token]);

  async function confirm() {
    const r = await fetch(`/api/public/unsubscribe/${token}`, { method: "POST" });
    setState(r.ok ? "done" : "invalid");
  }

  return (
    <div className="grid min-h-screen place-items-center bg-background px-4">
      <div className="w-full max-w-md text-center">
        <div className="mx-auto mb-4 grid size-10 place-items-center rounded-md bg-primary font-serif text-xl font-bold text-primary-foreground">K</div>
        <h1 className="text-xl font-semibold">KORTEX DIGITAL</h1>
        {state === "loading" && <p className="mt-4 text-sm text-muted-foreground">Chargement…</p>}
        {state === "invalid" && <p className="mt-4 text-sm">Ce lien n&apos;est pas valide. Écrivez-nous à contact@kortexdigital.net et nous retirerons votre adresse.</p>}
        {state === "ready" && (
          <>
            <p className="mt-4 text-sm">Ne plus recevoir de messages de KORTEX DIGITAL à l&apos;adresse <b>{email}</b> ?</p>
            <button onClick={confirm} className="mt-5 rounded-md bg-primary px-5 py-2 text-sm font-medium text-primary-foreground">Confirmer la désinscription</button>
          </>
        )}
        {state === "done" && <p className="mt-4 text-sm">C&apos;est fait : <b>{email}</b> ne recevra plus de message de notre part. Merci et désolé pour le dérangement.</p>}
      </div>
    </div>
  );
}
