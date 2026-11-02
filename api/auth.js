// Innlogging: GET = hvem er jeg, POST {action: login|logout|invitasjon|oppstart|bytt-passord}
import bcrypt from 'bcryptjs';
import { handler, body, send, q, sha, rid, normEpost, okEpost, HttpError, startSession, endSession,
  currentUser, requireUser, publicUser, checkOrigin, BOOTSTRAP_HASH } from './_lib.js';

const PW_MIN = 10;
function checkPw(pw){
  if (typeof pw !== 'string' || pw.length < PW_MIN) throw new HttpError(400, 'weak_password', `Passordet må ha minst ${PW_MIN} tegn.`);
  if (pw.length > 200) throw new HttpError(400, 'weak_password', 'Passordet er for langt.');
}

export default handler(async (req, res) => {
  checkOrigin(req);
  if (req.method === 'GET'){
    const u = await currentUser(req);
    const [{ n }] = await q(`select count(*)::int as n from brukere where pw_hash is not null`);
    return send(res, 200, { bruker: u ? publicUser(u) : null, harBrukere: n > 0 });
  }
  if (req.method !== 'POST') throw new HttpError(405, 'method', 'Ikke tillatt.');
  const b = body(req), action = b.action;

  if (action === 'login'){
    const epost = normEpost(b.epost);
    const rows = await q(`select * from brukere where epost = $1`, [epost]);
    const u = rows[0];
    if (u?.sperret_til && new Date(u.sperret_til) > new Date())
      throw new HttpError(429, 'locked', 'For mange feil forsøk. Prøv igjen om 15 minutter.');
    const ok = u?.pw_hash && typeof b.passord === 'string' && await bcrypt.compare(b.passord, u.pw_hash);
    if (!ok){
      if (u) await q(`update brukere set
        sperret_til = case when feil_forsok + 1 >= 5 then now() + interval '15 minutes' else sperret_til end,
        feil_forsok = case when feil_forsok + 1 >= 5 then 0 else feil_forsok + 1 end
        where id = $1`, [u.id]);
      throw new HttpError(401, 'bad_login', 'Feil e-post eller passord.');
    }
    await q(`update brukere set feil_forsok = 0, sperret_til = null where id = $1`, [u.id]);
    await startSession(res, u.id);
    return send(res, 200, { bruker: publicUser(u) });
  }

  if (action === 'logout'){
    await endSession(req, res);
    return send(res, 200, { ok: true });
  }

  if (action === 'invitasjon-info'){
    const rows = await q(`select epost, navn from brukere where invitasjon_hash = $1 and invitasjon_utloper > now()`, [sha(b.token || '')]);
    if (!rows[0]) throw new HttpError(404, 'bad_invite', 'Lenken er ugyldig eller har gått ut. Be administratoren om en ny.');
    return send(res, 200, rows[0]);
  }

  if (action === 'invitasjon'){
    checkPw(b.passord);
    const rows = await q(`select * from brukere where invitasjon_hash = $1 and invitasjon_utloper > now()`, [sha(b.token || '')]);
    const u = rows[0];
    if (!u) throw new HttpError(404, 'bad_invite', 'Lenken er ugyldig eller har gått ut. Be administratoren om en ny.');
    const hash = await bcrypt.hash(b.passord, 11);
    await q(`update brukere set pw_hash = $1, invitasjon_hash = null, invitasjon_utloper = null, feil_forsok = 0, sperret_til = null where id = $2`, [hash, u.id]);
    await q(`delete from sesjoner where bruker_id = $1`, [u.id]);
    await startSession(res, u.id);
    return send(res, 200, { bruker: publicUser(u) });
  }

  if (action === 'oppstart'){
    // Første administrator. Virker bare så lenge ingen administrator finnes, og krever engangskoden.
    const [{ n }] = await q(`select count(*)::int as n from brukere where rolle = 'admin'`);
    if (n > 0) throw new HttpError(409, 'already_setup', 'Portalen er allerede satt opp. Logg inn i stedet.');
    if (sha(String(b.kode || '').trim()) !== BOOTSTRAP_HASH) throw new HttpError(403, 'bad_code', 'Feil oppstartskode.');
    const epost = normEpost(b.epost), navn = String(b.navn || '').trim().slice(0, 100);
    if (!okEpost(epost)) throw new HttpError(400, 'bad_email', 'Skriv inn en gyldig e-postadresse.');
    if (!navn) throw new HttpError(400, 'bad_name', 'Skriv inn navnet ditt.');
    checkPw(b.passord);
    const id = 'u_' + rid(10), hash = await bcrypt.hash(b.passord, 11);
    await q(`insert into brukere(id, epost, navn, rolle, pw_hash) values($1, $2, $3, 'admin', $4)`, [id, epost, navn, hash]);
    await startSession(res, id);
    return send(res, 200, { bruker: { id, epost, navn, rolle: 'admin' } });
  }

  if (action === 'bytt-passord'){
    const me = await requireUser(req);
    checkPw(b.nytt);
    const [u] = await q(`select pw_hash from brukere where id = $1`, [me.id]);
    if (!u?.pw_hash || !(await bcrypt.compare(String(b.gammelt || ''), u.pw_hash))) throw new HttpError(400, 'bad_password', 'Nåværende passord er feil.');
    await q(`update brukere set pw_hash = $1 where id = $2`, [await bcrypt.hash(b.nytt, 11), me.id]);
    return send(res, 200, { ok: true });
  }

  throw new HttpError(400, 'bad_action', 'Ukjent handling.');
});
