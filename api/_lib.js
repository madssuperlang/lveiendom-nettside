// Felles kode for portal-API-et. Filer som starter med _ blir ikke egne endepunkter på Vercel.
import crypto from 'node:crypto';

export const COLS = ['eiendommer', 'leietakere', 'betalinger', 'gjoremal', 'forsikringer', 'poster', 'saldobalanser'];
export const ROLES = ['admin', 'skriv', 'les'];

// Engangskode for å opprette den første administratoren. Bare hashen ligger her.
export const BOOTSTRAP_HASH = '4fca24e2f839d3b4f7e4a09282476d16ba320a48decfca2fa49beb047c281a0f';

const SESSION_DAYS = 30;
const COOKIE = 'lv_sesjon';

/* ---------- database ---------- */
let _q = null;
export function setQuery(fn){ _q = fn; }           // brukes av lokale tester
export async function q(text, params = []){
  if (!_q){
    const { neon } = await import('@neondatabase/serverless');
    const url = process.env.DATABASE_URL || process.env.POSTGRES_URL;
    if (!url) throw Object.assign(new Error('DATABASE_URL mangler'), { status: 500, code: 'no_db' });
    const sql = neon(url);
    _q = (t, p) => sql.query(t, p);
  }
  return _q(text, params);
}

let ready = null;
export function ensureSchema(){
  if (!ready) ready = (async () => {
    await q(`create table if not exists brukere(
      id text primary key, epost text unique not null, navn text not null default '',
      rolle text not null default 'les', pw_hash text, invitasjon_hash text, invitasjon_utloper timestamptz,
      feil_forsok int not null default 0, sperret_til timestamptz, opprettet timestamptz not null default now())`);
    await q(`create table if not exists sesjoner(
      token_hash text primary key, bruker_id text not null references brukere(id) on delete cascade,
      utloper timestamptz not null, opprettet timestamptz not null default now())`);
    await q(`create table if not exists dokumenter(
      col text not null, id text not null, data jsonb not null default '{}'::jsonb,
      versjon int not null default 1, endret timestamptz not null default now(), primary key(col, id))`);
  })().catch(e => { ready = null; throw e; });
  return ready;
}

/* ---------- hjelpere ---------- */
export const sha = s => crypto.createHash('sha256').update(String(s)).digest('hex');
export const rid = (n = 16) => crypto.randomBytes(n).toString('base64url');
export const normEpost = e => String(e || '').trim().toLowerCase();
export const okEpost = e => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e) && e.length <= 200;

export class HttpError extends Error { constructor(status, code, msg){ super(msg || code); this.status = status; this.code = code; } }

export function send(res, status, body){
  res.setHeader('Cache-Control', 'no-store');
  res.status(status).json(body);
}

export function handler(fn){
  return async (req, res) => {
    try {
      await ensureSchema();
      await fn(req, res);
    } catch (e){
      const status = e.status || 500;
      if (status >= 500) console.error(e);
      send(res, status, { error: e.code || 'server_error', melding: status >= 500 ? 'Noe gikk galt på serveren.' : e.message });
    }
  };
}

export function body(req){
  const b = req.body;
  if (b && typeof b === 'object') return b;
  try { return JSON.parse(b || '{}'); } catch { return {}; }
}

/* ---------- sesjoner ---------- */
function readCookie(req, name){
  const h = req.headers.cookie || '';
  for (const part of h.split(';')){
    const [k, ...v] = part.trim().split('=');
    if (k === name) return decodeURIComponent(v.join('='));
  }
  return null;
}
function cookieStr(val, maxAge){
  return `${COOKIE}=${encodeURIComponent(val)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`;
}
export async function startSession(res, userId){
  const token = rid(32);
  await q(`insert into sesjoner(token_hash, bruker_id, utloper) values($1, $2, now() + ($3 || ' days')::interval)`, [sha(token), userId, String(SESSION_DAYS)]);
  await q(`delete from sesjoner where utloper < now()`);
  res.setHeader('Set-Cookie', cookieStr(token, SESSION_DAYS * 86400));
}
export async function endSession(req, res){
  const t = readCookie(req, COOKIE);
  if (t) await q(`delete from sesjoner where token_hash = $1`, [sha(t)]);
  res.setHeader('Set-Cookie', cookieStr('', 0));
}
export async function currentUser(req){
  const t = readCookie(req, COOKIE);
  if (!t) return null;
  const rows = await q(`select b.id, b.epost, b.navn, b.rolle from sesjoner s join brukere b on b.id = s.bruker_id
                        where s.token_hash = $1 and s.utloper > now()`, [sha(t)]);
  return rows[0] || null;
}
export async function requireUser(req, roles = ROLES){
  const u = await currentUser(req);
  if (!u) throw new HttpError(401, 'not_logged_in', 'Du er ikke logget inn.');
  if (!roles.includes(u.rolle)) throw new HttpError(403, 'forbidden', 'Du har ikke tilgang til dette.');
  return u;
}
export const publicUser = u => ({ id: u.id, epost: u.epost, navn: u.navn, rolle: u.rolle });

/* Samme opprinnelse for alt som endrer noe (enkel CSRF-beskyttelse i tillegg til SameSite). */
export function checkOrigin(req){
  if (req.method === 'GET') return;
  const o = req.headers.origin, h = req.headers['x-forwarded-host'] || req.headers.host;
  if (o && h && new URL(o).host !== h) throw new HttpError(403, 'bad_origin', 'Ugyldig opprinnelse.');
}
