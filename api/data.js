// Data: GET = alle dokumenter, POST {op: set|update|delete|add|import, col, id, data}
import { handler, body, send, q, rid, HttpError, requireUser, checkOrigin, COLS } from './_lib.js';

const okId = id => typeof id === 'string' && /^[A-Za-z0-9_\-.~:@+]{1,200}$/.test(id);
const okData = d => d && typeof d === 'object' && !Array.isArray(d) && JSON.stringify(d).length < 400000;

export default handler(async (req, res) => {
  checkOrigin(req);
  if (req.method === 'GET'){
    await requireUser(req);
    const rows = await q(`select col, id, data, versjon, endret from dokumenter order by col, id`);
    const out = Object.fromEntries(COLS.map(c => [c, []]));
    for (const r of rows) if (out[r.col]) out[r.col].push({ id: r.id, ...r.data });
    return send(res, 200, { data: out, tid: new Date().toISOString() });
  }
  if (req.method !== 'POST') throw new HttpError(405, 'method', 'Ikke tillatt.');
  const b = body(req);

  if (b.op === 'import'){
    // Engangsflytting av data fra den gamle portalen. Bare for administrator, og bare til tomme samlinger.
    await requireUser(req, ['admin']);
    const docs = Array.isArray(b.docs) ? b.docs : [];
    const [{ n }] = await q(`select count(*)::int as n from dokumenter`);
    if (n > 0 && !b.tving) throw new HttpError(409, 'not_empty', 'Databasen har allerede data.');
    let k = 0;
    for (const d of docs){
      if (!COLS.includes(d.col) || !okId(d.id) || !okData(d.data)) continue;
      await q(`insert into dokumenter(col, id, data) values($1, $2, $3::jsonb) on conflict (col, id) do nothing`, [d.col, d.id, JSON.stringify(d.data)]);
      k++;
    }
    return send(res, 200, { importert: k });
  }

  const me = await requireUser(req, ['admin', 'skriv']);
  if (!COLS.includes(b.col)) throw new HttpError(400, 'bad_col', 'Ukjent samling.');

  if (b.op === 'add'){
    if (!okData(b.data)) throw new HttpError(400, 'bad_data', 'Ugyldige data.');
    const id = rid(9);
    await q(`insert into dokumenter(col, id, data) values($1, $2, $3::jsonb)`, [b.col, id, JSON.stringify(b.data)]);
    return send(res, 200, { id });
  }
  if (!okId(b.id)) throw new HttpError(400, 'bad_id', 'Ugyldig id.');
  if (b.op === 'set'){
    if (!okData(b.data)) throw new HttpError(400, 'bad_data', 'Ugyldige data.');
    await q(`insert into dokumenter(col, id, data) values($1, $2, $3::jsonb)
             on conflict (col, id) do update set data = excluded.data, versjon = dokumenter.versjon + 1, endret = now()`,
      [b.col, b.id, JSON.stringify(b.data)]);
    return send(res, 200, { id: b.id });
  }
  if (b.op === 'update'){
    if (!okData(b.data)) throw new HttpError(400, 'bad_data', 'Ugyldige data.');
    const r = await q(`update dokumenter set data = data || $3::jsonb, versjon = versjon + 1, endret = now()
                       where col = $1 and id = $2 returning id`, [b.col, b.id, JSON.stringify(b.data)]);
    if (!r.length) throw new HttpError(404, 'not_found', 'Fant ikke dokumentet.');
    return send(res, 200, { id: b.id });
  }
  if (b.op === 'delete'){
    await q(`delete from dokumenter where col = $1 and id = $2`, [b.col, b.id]);
    return send(res, 200, { id: b.id });
  }
  throw new HttpError(400, 'bad_op', 'Ukjent operasjon.');
});
