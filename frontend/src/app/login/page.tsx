"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { Spin, useAction } from "@/components/shared";

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"phone" | "code">("phone");
  const { busy, run } = useAction();

  useEffect(() => {
    // Auth désactivée (dev) ou déjà connecté : direction le tableau de bord.
    fetch("/api/auth/me").then((r) => r.ok && router.replace("/"));
  }, [router]);

  async function send() {
    const r = await run("send", () => api("/api/auth/request-otp", { method: "POST", json: { phone } }));
    if (r) setStep("code");
  }
  async function verify() {
    const r = await run("verify", () => api("/api/auth/verify-otp", { method: "POST", json: { phone, code } }));
    if (r) router.replace("/");
  }

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center">
          <div className="mx-auto mb-2 grid size-10 place-items-center rounded-md bg-primary font-serif text-xl font-bold text-primary-foreground">K</div>
          <CardTitle>KORTEX Prospect</CardTitle>
          <p className="text-sm text-muted-foreground">Connexion par code WhatsApp</p>
        </CardHeader>
        <CardContent className="space-y-4">
          {step === "phone" ? (
            <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); send(); }}>
              <Label htmlFor="phone">Numéro WhatsApp</Label>
              <Input id="phone" inputMode="tel" autoFocus placeholder="07 12 11 62 58" value={phone} onChange={(e) => setPhone(e.target.value)} />
              <Button className="w-full" disabled={!phone || busy === "send"}><Spin on={busy === "send"} /><MessageCircle className="size-4" /> Recevoir un code</Button>
              <p className="text-[11px] text-muted-foreground">Seuls les numéros autorisés reçoivent un code.</p>
            </form>
          ) : (
            <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); verify(); }}>
              <Label htmlFor="code">Code reçu sur WhatsApp</Label>
              <Input id="code" inputMode="numeric" autoComplete="one-time-code" autoFocus maxLength={6} placeholder="123456"
                className="text-center text-lg tracking-[0.4em]" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
              <Button className="w-full" disabled={code.length < 6 || busy === "verify"}><Spin on={busy === "verify"} /> Se connecter</Button>
              <button type="button" className="w-full text-xs text-muted-foreground underline" onClick={() => { setStep("phone"); setCode(""); }}>Changer de numéro / renvoyer</button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
