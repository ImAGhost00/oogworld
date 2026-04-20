"use client";

import { useEffect, useState } from "react";
import LabelInput from "@/components/ui/label-input";
import { Particles } from "@/components/ui/particles";

const TOKEN_KEY = "oogworld_name_token";
const TOKEN_EXP_KEY = "oogworld_name_token_exp";
const NAME_KEY = "oogworld_display_name";
const TOKEN_TTL_MS = 1000 * 60 * 60 * 24 * 7;

function isNightNow() {
  const hour = new Date().getHours();
  return hour >= 19 || hour < 6;
}

function createToken() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "token_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export default function Page() {
  const [ready, setReady] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [draftName, setDraftName] = useState("");
  const [isNight, setIsNight] = useState(false);

  useEffect(() => {
    const updateNight = () => setIsNight(isNightNow());
    updateNight();
    const timer = window.setInterval(updateNight, 60 * 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const token = sessionStorage.getItem(TOKEN_KEY);
    const expRaw = sessionStorage.getItem(TOKEN_EXP_KEY);
    const savedName = sessionStorage.getItem(NAME_KEY) || "";
    const exp = Number(expRaw || "0");

    if (!token || !savedName || !exp || Date.now() >= exp) {
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_EXP_KEY);
      sessionStorage.removeItem(NAME_KEY);
      setDisplayName("");
      setDraftName(savedName);
      setReady(true);
      return;
    }

    setDisplayName(savedName);
    setReady(true);
  }, []);

  function submitName(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const cleaned = draftName.trim().replace(/[<>]/g, "").slice(0, 24);
    if (!cleaned) return;

    const token = createToken();
    const expiresAt = Date.now() + TOKEN_TTL_MS;

    sessionStorage.setItem(TOKEN_KEY, token);
    sessionStorage.setItem(TOKEN_EXP_KEY, String(expiresAt));
    sessionStorage.setItem(NAME_KEY, cleaned);
    setDisplayName(cleaned);
  }

  function resetIdentity() {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_EXP_KEY);
    sessionStorage.removeItem(NAME_KEY);
    setDisplayName("");
    setDraftName("");
  }

  if (!ready) {
    return null;
  }

  if (!displayName) {
    return (
      <main className="relative min-h-screen flex items-center justify-center p-6 overflow-hidden">
        {isNight && (
          <div className="pointer-events-none absolute inset-0 z-0">
            <Particles quantity={240} staticity={45} ease={55} size={0.8} color="#f0ebe5" className="h-full w-full" />
          </div>
        )}
        <form onSubmit={submitName} className="relative z-10 w-full max-w-md rounded-xl border border-border bg-[#2d3a2e]/70 p-6 space-y-4">
          <h1 className="text-xl font-semibold">Choose your name</h1>
          <p className="text-sm text-muted-foreground">Required on new launch or when your session token expires.</p>
          <LabelInput
            value={draftName}
            onChange={(e) => setDraftName(e.target.value)}
            label="Display Name"
            placeholder="Pick your name"
            ringColor="emerald"
            maxLength={24}
            autoFocus
          />
          <button
            type="submit"
            className="w-full rounded-lg bg-primary px-4 py-2 font-semibold text-primary-foreground disabled:opacity-60"
            disabled={!draftName.trim()}
          >
            Continue
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="relative min-h-screen p-6 space-y-6 overflow-hidden">
      {isNight && (
        <div className="pointer-events-none absolute inset-0 z-0">
          <Particles quantity={260} staticity={45} ease={55} size={0.8} color="#f0ebe5" className="h-full w-full" />
        </div>
      )}
      <section className="relative z-10 mx-auto w-full max-w-4xl rounded-xl border border-border bg-[#2d3a2e]/70 p-4 flex items-center justify-between gap-4">
        <p className="text-sm md:text-base">Signed in as <span className="font-semibold text-primary">{displayName}</span></p>
        <button type="button" onClick={resetIdentity} className="rounded-lg border border-border px-3 py-2 text-sm hover:bg-white/5">
          Change Name
        </button>
      </section>
      <section className="relative z-10 mx-auto w-full max-w-4xl rounded-xl border border-border bg-[#2d3a2e]/70 p-6">
        <h2 className="text-lg font-semibold">Night Sky Mode</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Stars are rendered automatically from 7pm to 6am using the integrated particles layer.
        </p>
      </section>
    </main>
  );
}
