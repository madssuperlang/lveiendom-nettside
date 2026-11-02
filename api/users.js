// Eiere: GET = liste (alle innloggede), POST {action: inviter|ny-lenke|rolle|fjern} (bare administrator)
import { handler, body, send, q, sha, rid, normEpost, okEpost, HttpError, requireUser, checkOrigin, ROLES } from './_lib.js';

const INVITE_DAYS = 7;

export default handler(async (req, res) => {
  checkOrigin(req);
  if (req.method === 'GET'){
    const me = await requireUser(req);
    const rows = await q(`select id, epost, navn, rolle, (pw_hash is not null) as aktiv,
                          (invitasjon_hash is not null and invitasjon_utloper > now()) as invitert from brukere order by navn`);
    return send(res, 200, { brukere: rows.map(r => me.rolle === 'admin' ? r : { id: r.id, navn: r.navn, rolle: r.rolle }) });
  }
  if (req.method !== 'POST') throw new HttpError(405, 'method', 'Ikke tillatt.');
  const me = await requireUser(req, ['admin']);
  const b = body(req);
  const lenke = token => `/?invitasjon=${encodeURIComponent(token)}`;

  if (b.action === 'inviter'){
    const epost = normEpost(b.epost), navn = String(b.navn || '').trim().slice(0, 100), rolle = ROLES.includes(b.rolle) ? b.rolle : 'les';
    if (!okEpost(epost)) throw new HttpError(400, 'bad_email', 'Skriv inn en gyldig e-postadresse.');
    if (!navn) throw new HttpError(400, 'bad_name', 'Skriv inn navnet.');
    const finnes = await q(`select id from brukere where epost = $1`, [epost]);
    if (finnes.length) throw new HttpError(409, 'exists', 'Det finnes allerede en eier med den e-postadressen.');
    const token = rid(24), id = 'u_' + rid(10);
    await q(`insert into brukere(id, epost, navn, rolle, invitasjon_hash, invitasjon_utloper)
             values($1, $2, $3, $4, $5, now() + ($6 || ' days')::interval)`, [id, epost, navn, rolle, sha(token), String(INVITE_DAYS)]);
    return send(res, 200, { id, lenke: lenke(token), dager: INVITE_DAYS });
  }

  const [u] = await q(`select id, rolle from brukere where id = $1`, [String(b.id || '')]);
  if (!u) throw new HttpError(404, 'not_found', 'Fant ikke eieren.');

  if (b.action === 'ny-lenke'){
    // Ny invitasjon, også brukt til å nullstille glemt passord.
    const token = rid(24);
    await q(`update brukere set invitasjon_hash = $1, invitasjon_utloper = now() + ($2 || ' days')::interval where id = $3`, [sha(token), String(INVITE_DAYS), u.id]);
    return send(res, 200, { lenke: lenke(token), dager: INVITE_DAYS });
  }
  if (b.action === 'rolle'){
    if (!ROLES.includes(b.rolle)) throw new HttpError(400, 'bad_role', 'Ukjent rolle.');
    if (u.id === me.id && b.rolle !== 'admin') throw new HttpError(400, 'self', 'Du kan ikke fjerne din egen administratortilgang.');
    await q(`update brukere set rolle = $1 where id = $2`, [b.rolle, u.id]);
    return send(res, 200, { ok: true });
  }
  if (b.action === 'fjern'){
    if (u.id === me.id) throw new HttpError(400, 'self', 'Du kan ikke fjerne deg selv.');
    await q(`delete from brukere where id = $1`, [u.id]);
    return send(res, 200, { ok: true });
  }
  throw new HttpError(400, 'bad_action', 'Ukjent handling.');
});
