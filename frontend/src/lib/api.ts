// Appels same-origin : le serveur Next relaie /api/* vers FastAPI (lib/server/proxy.ts).
export const API = "";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T = any>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init || {};
  const res = await fetch(API + path, {
    ...rest,
    headers: json !== undefined ? { "Content-Type": "application/json", ...(rest.headers || {}) } : rest.headers,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (res.status === 401 && typeof window !== "undefined" && !location.pathname.startsWith("/login")) {
    location.href = "/login";
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const d = await res.json();
      msg = typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail ?? d);
    } catch {}
    throw new ApiError(res.status, msg);
  }
  const ct = res.headers.get("content-type") || "";
  return (ct.includes("json") ? res.json() : res.text()) as Promise<T>;
}

export const fetcher = (path: string) => api(path);

/** Télécharge un fichier renvoyé par l'API (export PDF/DOCX, brouillon .eml). */
export async function download(path: string, fallbackName = "fichier") {
  const res = await fetch(API + path);
  if (!res.ok) {
    let msg = res.statusText;
    try {
      msg = (await res.json()).detail;
    } catch {}
    throw new ApiError(res.status, msg);
  }
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") || "";
  const name = /filename="?([^"]+)"?/.exec(cd)?.[1] || fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export type Criterion = { label: string; score: number; max: number; reason: string };
export type Analysis = {
  method: "heuristic" | "llm";
  total: number;
  criteria: Record<string, Criterion>;
  recommended_profile?: string;
  relevant_shalom?: boolean;
  relevant_kortex?: boolean;
  matched?: string[];
  contact_to_target?: string;
  documents_to_attach?: string[];
  approach?: string;
  language?: string;
  red_flags?: string[];
  summary?: string;
  model?: string;
};

export type Opportunity = {
  id: number;
  kind: "job" | "freelance" | "b2b";
  profile_key: string;
  title: string;
  company_name: string;
  company_id: number | null;
  contract_type: string;
  salary: string;
  currency: string;
  location: string;
  remote: boolean | null;
  language: string;
  published_at: string | null;
  deadline: string | null;
  apply_url: string;
  source: string;
  source_url: string;
  needs_verification: boolean;
  status: string;
  score: number | null;
  score_method?: string;
  skills: string[];
  excerpt?: string;
  description?: string;
  analysis?: Analysis | null;
  notes?: string;
  next_action: string;
  next_action_date: string | null;
  collected_at: string;
  last_checked_at: string;
  generated?: Generated[];
  applications?: Application[];
  activities?: Activity[];
};

export type Contact = {
  id: number;
  kind: string;
  value: string;
  label: string;
  person_name: string;
  confidence: "verified" | "found_unverified" | "estimated";
  source_url: string;
  found_at: string;
};

export type Company = {
  id: number;
  name: string;
  domain: string | null;
  website: string | null;
  sector: string;
  country: string;
  city: string;
  status: string;
  score: number | null;
  score_method?: string;
  source_url: string;
  source_name: string;
  collected_at: string;
  verified_at: string | null;
  next_action: string;
  next_action_date: string | null;
  emails: number;
  verified_emails: number;
  description?: string;
  address?: string;
  notes?: string;
  analysis?: Analysis | null;
  contacts?: Contact[];
  opportunities?: Opportunity[];
  generated?: Generated[];
  applications?: Application[];
  activities?: Activity[];
};

export type Generated = {
  id: number;
  doc_type: "cover_letter" | "b2b_proposal" | "email";
  profile_key: string;
  language: string;
  opportunity_id: number | null;
  company_id: number | null;
  subject: string;
  content: string;
  model_used: string;
  edited: boolean;
  created_at: string;
  updated_at: string;
};

export type Application = {
  id: number;
  profile_key: string;
  opportunity_id: number | null;
  company_id: number | null;
  channel: string;
  recipient: string;
  cc: string;
  subject: string;
  body: string;
  letter_id: number | null;
  attachment_ids: number[];
  attach_letter_format: string;
  status: string;
  draft_provider: string;
  draft_ref: string;
  sent_at: string | null;
  created_at: string;
  updated_at: string;
  target_title?: string;
  target_company?: string;
};

export type Activity = {
  id: number;
  type: string;
  summary: string;
  company_id: number | null;
  opportunity_id: number | null;
  application_id: number | null;
  occurred_at: string;
};

export type Doc = {
  id: number;
  profile_key: string | null;
  category: string;
  category_label: string;
  language: string;
  title: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  has_text: boolean;
  notes: string;
  created_at: string;
};

export const STATUS_LABELS: Record<string, string> = {
  decouverte: "Découverte",
  a_qualifier: "À qualifier",
  pertinent: "Pertinent",
  lettre_a_generer: "Lettre à générer",
  pret_a_postuler: "Prêt à postuler",
  envoyee_manuellement: "Envoyée manuellement",
  relance_necessaire: "Relance nécessaire",
  reponse_recue: "Réponse reçue",
  rdv_programme: "Rendez-vous programmé",
  entretien_realise: "Entretien réalisé",
  negociation: "Négociation",
  gagne: "Gagné",
  refuse: "Refusé",
  archive: "Archivé",
};

export const KIND_LABELS: Record<string, string> = { job: "Emploi", freelance: "Freelance", b2b: "B2B" };
export const PROFILE_LABELS: Record<string, string> = { shalom: "Shalom Tehe", kortex: "KORTEX DIGITAL" };
export const DOC_TYPE_LABELS: Record<string, string> = {
  cover_letter: "Lettre de motivation",
  b2b_proposal: "Proposition commerciale",
  email: "Email d'accompagnement",
};
export const CONFIDENCE_LABELS: Record<string, string> = {
  verified: "Publié sur le site officiel",
  found_unverified: "Trouvé, non vérifié",
  estimated: "Estimé — non confirmé",
};
export const CONTACT_LABELS: Record<string, string> = {
  general: "Général",
  rh: "RH / recrutement",
  it: "IT / informatique",
  direction: "Direction",
  partenariat: "Partenariat / achats",
};

export function fmtDate(d: string | null | undefined, withTime = false) {
  if (!d) return "—";
  const date = new Date(d);
  return date.toLocaleDateString("fr-FR", withTime ? { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" } : { day: "2-digit", month: "short", year: "numeric" });
}

export const APP_STATUS: Record<string, string> = {
  brouillon: "Brouillon",
  draft_cree: "Brouillon prêt (non envoyé)",
  envoyee: "Envoyée manuellement",
  annulee: "Annulée",
};
