// FINN: POST {url} = henter en FINN-annonse og gir tilbake teksten, så portalen kan lese ut pris, fellesgjeld osv.
// Bare innloggede brukere, og bare adresser på finn.no (ingen andre nettsteder kan hentes herfra).
import { handler, body, send, HttpError, requireUser, checkOrigin } from './_lib.js';

const VERTER = new Set(['finn.no', 'www.finn.no', 'm.finn.no']);
const MAKS_TEGN = 3_000_000;

export function finnUrl(inn){
  const s = String(inn || '').trim();
  if (/^\d{6,12}$/.test(s)) return new URL('https://www.finn.no/' + s);
  let u;
  try { u = new URL(/^https?:\/\//i.test(s) ? s : 'https://' + s); } catch { throw new HttpError(400, 'bad_url', 'Lim inn en lenke til en FINN-annonse eller en FINN-kode.'); }
  if (!VERTER.has(u.hostname.toLowerCase())) throw new HttpError(400, 'bad_url', 'Lenken må gå til finn.no.');
  u.protocol = 'https:'; u.username = ''; u.password = ''; u.port = '';
  return u;
}

const ENT = { amp:'&', lt:'<', gt:'>', quot:'"', apos:"'", nbsp:' ', shy:'', ndash:'–', mdash:'—', middot:'·', sup2:'²',
  aelig:'æ', oslash:'ø', aring:'å', AElig:'Æ', Oslash:'Ø', Aring:'Å', eacute:'é', hellip:'…' };
export function dekod(s){
  return s.replace(/&(#x[0-9a-f]+|#\d+|[a-z0-9]+);/gi, (m, e) => {
    if (e[0] !== '#') return ENT[e] ?? m;
    const n = e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
    try { return String.fromCodePoint(n); } catch { return m; }
  });
}

const meta = (html, prop) => {
  const m = html.match(new RegExp(`<meta[^>]+(?:property|name)=["']${prop}["'][^>]*>`, 'i'));
  const c = m && m[0].match(/content=["']([^"']*)["']/i);
  return c ? dekod(c[1]).trim() : '';
};

export function tilTekst(html){
  let s = html.replace(/<(script|style|noscript|svg|template|head)\b[\s\S]*?<\/\1\s*>/gi, ' ');
  s = s.replace(/<br\s*\/?>/gi, '\n')
       .replace(/<\/?(div|p|li|ul|ol|dl|dt|dd|h[1-6]|tr|td|th|table|section|article|header|footer|aside|nav|main|button|label|figure|figcaption|summary|details)\b[^>]*>/gi, '\n')
       .replace(/<\/span>/gi, ' ').replace(/<[^>]+>/g, '');
  return dekod(s).split('\n').map(l => l.replace(/[\s   ]+/g, ' ').trim()).filter(Boolean).join('\n');
}

async function hent(url){
  let u = url;
  for (let i = 0; i < 5; i++){
    let r;
    try {
      r = await fetch(u, { redirect: 'manual', signal: AbortSignal.timeout(8000), headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'nb-NO,nb;q=0.9,no;q=0.8' } });
    } catch { throw new HttpError(502, 'finn_down', 'Fikk ikke kontakt med FINN. Prøv igjen, eller lim inn annonseteksten.'); }
    if (r.status >= 300 && r.status < 400 && r.headers.get('location')){
      u = finnUrl(new URL(r.headers.get('location'), u).href);
      continue;
    }
    if (r.status === 404 || r.status === 410) throw new HttpError(404, 'finn_404', 'Fant ikke annonsen. Den kan være solgt eller fjernet.');
    if (!r.ok) throw new HttpError(502, 'finn_blocked', 'FINN ville ikke gi fra seg annonsen akkurat nå. Lim inn annonseteksten i stedet.');
    const html = (await r.text()).slice(0, MAKS_TEGN);
    return { html, url: u.href };
  }
  throw new HttpError(502, 'finn_redirect', 'FINN sendte oss rundt i ring. Lim inn annonseteksten i stedet.');
}

export default handler(async (req, res) => {
  checkOrigin(req);
  if (req.method !== 'POST') throw new HttpError(405, 'method', 'Ikke tillatt.');
  await requireUser(req);
  const { html, url } = await hent(finnUrl(body(req).url));
  const tekst = tilTekst(html);
  if (tekst.length < 200) throw new HttpError(502, 'finn_empty', 'Annonsen kom tom tilbake fra FINN. Lim inn annonseteksten i stedet.');
  return send(res, 200, {
    url, tittel: meta(html, 'og:title') || (html.match(/<title[^>]*>([^<]*)/i)?.[1] || '').trim(),
    bilde: meta(html, 'og:image'), tekst: tekst.slice(0, 200000)
  });
});
