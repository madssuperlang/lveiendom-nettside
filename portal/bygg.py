# Lager portal/index.html fra Claude-versjonen (kilde-claude.html):
# bytter ut Claude-databasen med egen API, legger til innlogging, eier-administrasjon og manuell saldobalanse.
import re, pathlib
P = pathlib.Path(__file__).parent
s = (P / 'kilde-claude.html').read_text()

def rep(a, b, n=1):
    global s
    c = s.count(a)
    assert c == n, (c, a[:80])
    s = s.replace(a, b)

def cut(start, end, new):
    """Bytt ut alt fra og med start til (ikke med) end."""
    global s
    i = s.index(start); j = s.index(end, i)
    s = s[:i] + new + s[j:]

# ---------- hode ----------
rep('<!doctype html><html><head>', '<!doctype html><html lang="nb"><head><title>LV Eiendom – eierportal</title><meta name="robots" content="noindex,nofollow"><link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png"><link rel="icon" href="/favicon.ico" sizes="any"><link rel="apple-touch-icon" href="/apple-touch-icon.png">')
rep('<title>LV Eiendom</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n', '')

# ---------- ekstra stil: innloggingsside ----------
rep('.toast{position:fixed', '''.auth{min-height:100vh;display:grid;place-items:center;padding:24px}
.auth .card{width:min(440px,100%);padding:32px}
.auth .brand{padding:0 0 22px}
.auth form{display:flex;flex-direction:column;gap:14px}
.auth .btn{width:100%;margin-top:6px}
.auth p{margin:0 0 6px;color:var(--mut)}
.me .acts{display:flex;gap:12px;margin-top:4px}
.me .acts .linkbtn{font-size:13px}
.copy{display:flex;gap:8px}.copy .inp{font-size:14px}
.toast{position:fixed''')

# ---------- skjema for saldobalanse (manuell) ----------
rep('''  poster:{ new:'Ny post', edit:'Rediger post', f:[''', '''  saldobalanser:{ new:'Legg inn saldobalanse', edit:'Rediger saldobalanse', f:[
    {k:'periode',l:'Måned',t:'month',req:1,hint:'Saldobalansen per utgangen av måneden'},
    {k:'restgjeld',l:'Restgjeld bank',u:'kr',t:'num',hint:'Konto 2200–2249'},
    {k:'gjeldTilOss',l:'Gjeld til oss (eierne)',u:'kr',t:'num',hint:'Aksjonærlån og mellomregning'},
    {k:'bank',l:'Bankinnskudd',u:'kr',t:'num',hint:'Konto 1900–1999'},
    {k:'inntekter',l:'Inntekter hittil i år',u:'kr',t:'num'},
    {k:'kostnader',l:'Kostnader hittil i år',u:'kr',t:'num',hint:'Inkludert renter'},
    {k:'resultat',l:'Resultat hittil i år',u:'kr',t:'num',hint:'Tomt = inntekter minus kostnader'},
    {k:'notat',l:'Merknader',t:'textarea',full:1}
  ]},
  poster:{ new:'Ny post', edit:'Rediger post', f:[''')

# saldobalanse lagres med måneden som id
rep('''      if (docId) await db.collection(col).doc(docId).set(body); else await db.collection(col).add(body);''',
    '''      const fid = docId || (col === 'saldobalanser' ? vals.periode : null);
      if (fid) await db.collection(col).doc(fid).set(body); else await db.collection(col).add(body);''')
rep('''    if (doc){ const {id, ...rest} = doc; await db.collection(col).doc(id).set({...rest, ...vals, ...meta}); }''',
    '''    if (doc && col === 'saldobalanser' && vals.periode && vals.periode !== doc.id){
      const {id, ...rest} = doc; await db.collection(col).doc(vals.periode).set({...rest, ...vals, ...meta}); await db.collection(col).doc(id).delete();
    } else if (doc){ const {id, ...rest} = doc; await db.collection(col).doc(id).set({...rest, ...vals, ...meta}); }''')

# ---------- ny saldobalanse-visning ----------
cut('/* ---------- saldobalanse ---------- */', '/* ---------- ruting og rendering ---------- */', r'''/* ---------- saldobalanse (fylles inn for hånd) ---------- */
let sbYM = null;
function sbTall(d){
  const inn = num(d.inntekter), kost = num(d.kostnader);
  return { rest: num(d.restgjeld), oss: num(d.gjeldTilOss), bank: num(d.bank), inn, kost,
    res: d.resultat != null && d.resultat !== '' ? num(d.resultat) : inn - kost };
}
const SB_TEKST = 'Last opp saldobalansen som CSV fra regnskapssystemet. Portalen leser kontoene og fyller ut restgjeld, gjeld til eierne, bank, inntekter, kostnader og resultat.';
/* tall på norsk format: «1 297 675,00», «-30 000,00», «(1 234,50)» */
function sbTallFra(v){
  let t = String(v ?? '').replace(/["\s  ]/g, '');
  if (!t || t === '-') return null;
  let neg = false;
  if (/^\(.*\)$/.test(t)){ neg = true; t = t.slice(1, -1); }
  if (t.endsWith('-')){ neg = !neg; t = t.slice(0, -1); }
  if (t.includes(',')) t = t.replace(/\./g, '').replace(',', '.');
  const n = Number(t); return isFinite(n) ? (neg ? -n : n) : null;
}
function sbDelLinje(l, sep){
  const out = []; let cur = '', q = false;
  for (let i = 0; i < l.length; i++){
    const c = l[i];
    if (c === '"'){ if (q && l[i + 1] === '"'){ cur += '"'; i++; } else q = !q; }
    else if (c === sep && !q){ out.push(cur); cur = ''; }
    else cur += c;
  }
  out.push(cur); return out.map(x => x.trim());
}
function sbLesCsv(tekst){
  const rader = tekst.replace(/^﻿/, '').split(/\r?\n/).filter(l => l.trim());
  if (!rader.length) throw new Error('Filen er tom.');
  const sep = [';', '\t', ','].map(s => [s, (rader[0].match(new RegExp(s === '\t' ? '\t' : s, 'g')) || []).length]).sort((a, b) => b[1] - a[1])[0][0];
  const tabell = rader.map(l => sbDelLinje(l, sep));
  const hi = tabell.findIndex(r => r.some(c => /konto/i.test(c)));
  const hode = hi >= 0 ? tabell[hi].map(c => c.toLowerCase()) : [];
  const finn = re => hode.findIndex(c => re.test(c));
  let kNr = finn(/kontonr|^konto$|kontonummer/), kNavn = finn(/navn|tekst|beskrivelse/), kUB = finn(/^ub$|utgående|utg\. ?saldo|^saldo/);
  if (kNr < 0) kNr = 0; if (kNavn < 0) kNavn = 1;
  const linjer = [];
  for (const r of tabell.slice(hi + 1)){
    const nr = (r[kNr] || '').replace(/\D/g, '');
    if (!/^\d{4,}$/.test(nr)) continue;
    let ub = kUB >= 0 ? sbTallFra(r[kUB]) : null;
    if (ub == null){ for (let j = r.length - 1; j > kNavn; j--){ const v = sbTallFra(r[j]); if (v != null){ ub = v; break; } } }
    if (ub == null) continue;
    linjer.push({ konto: nr.slice(0, 4), navn: r[kNavn] || '', ub: Math.round(ub * 100) / 100 });
  }
  if (!linjer.length) throw new Error('Fant ingen kontolinjer. Sjekk at filen er en saldobalanse med kontonummer og saldo.');
  return linjer;
}
const EIER_RE = /gjeld til|aksjonær|eier|mellomregning|holding|nærstående/i;
function sbGruppe(l){
  const k = +l.konto;
  if (k < 1900) return 'eiendel';
  if (k < 2000) return 'bank';
  if (k < 2100) return 'egenkapital';
  if (k >= 2200 && k < 2250) return 'restgjeld';
  if ((k >= 2250 && k < 2300) || (k >= 2900 && k < 3000 && EIER_RE.test(l.navn))) return 'eiere';
  if (k < 3000) return 'annenGjeld';
  if (k < 4000 || (k >= 8000 && k < 8100)) return 'inntekt';
  return 'kostnad';
}
function sbBeregn(linjer){
  const s = g => linjer.filter(l => sbGruppe(l) === g).reduce((a, l) => a + l.ub, 0);
  const r2 = n => Math.round(n * 100) / 100;
  const inn = r2(-s('inntekt')), kost = r2(s('kostnad'));
  return { restgjeld: r2(-s('restgjeld')), gjeldTilOss: r2(-s('eiere')), bank: r2(s('bank')), inntekter: inn, kostnader: kost, resultat: r2(inn - kost) };
}
function sbGjettYM(filnavn, tekst){
  const m = String(filnavn).match(/(20\d{2})[-_.]?(\d{2})[-_.]?(\d{2})/);
  if (m){ const d = new Date(+m[1], +m[2] - 1, +m[3] - 10); return d.getFullYear() + '-' + pad(d.getMonth() + 1); }
  let best = null;
  for (const x of String(tekst).slice(0, 4000).matchAll(/\b(\d{1,2})\.(\d{1,2})\.(20\d{2})\b/g)){ const ym = x[3] + '-' + pad(+x[2]); if (+x[2] >= 1 && +x[2] <= 12 && (!best || ym > best)) best = ym; }
  return best || shiftYM(curYM(), -1);
}
async function sbLesFil(file){
  const buf = await file.arrayBuffer();
  let t = new TextDecoder('utf-8').decode(buf);
  if (t.includes('�')) t = new TextDecoder('windows-1252').decode(buf);
  return t;
}
async function sbImporter(file){
  if (!file) return;
  if (!/\.(csv|txt|skv)$/i.test(file.name)) return toast('Velg en CSV-fil. Excel-filer må lagres som CSV først.', true);
  try {
    const tekst = await sbLesFil(file), linjer = sbLesCsv(tekst), tall = sbBeregn(linjer), periode = sbGjettYM(file.name, tekst);
    const finnes = (S.saldobalanser || []).some(x => x.periode === periode);
    openForm('saldobalanser', null, {periode, ...tall}, null,
      `<div class="note-bar small" style="margin:-6px 0 18px">Lest ${linjer.length} kontoer fra <b>${esc(file.name)}</b>. Sjekk måneden og tallene, og trykk Lagre.${finnes ? ' Det finnes allerede en saldobalanse for ' + mLabel(periode) + ', og den blir erstattet hvis du beholder samme måned.' : ''}</div>`);
    M.extraVals = { linjer, filnavn: file.name, kilde: 'csv' };
  } catch (e){ toast(e.message || 'Kunne ikke lese filen.', true); }
}
const SB_GRUPPER = [['eiendel', 'Eiendeler', 1], ['bank', 'Bank', 1], ['restgjeld', 'Lån fra bank', -1], ['eiere', 'Gjeld til eierne', -1], ['annenGjeld', 'Annen gjeld', -1], ['egenkapital', 'Egenkapital', -1], ['inntekt', 'Inntekter', -1], ['kostnad', 'Kostnader', 1]];
function sbKontoer(d){
  const L = Array.isArray(d.linjer) ? d.linjer.filter(l => l && Math.abs(num(l.ub)) >= 0.5) : [];
  if (!L.length) return '';
  const del = SB_GRUPPER.map(([g, navn, fortegn]) => {
    const rows = L.filter(l => sbGruppe(l) === g); if (!rows.length) return '';
    const sumG = rows.reduce((a, l) => a + num(l.ub), 0) * fortegn;
    return `<tr class="em"><td colspan="2">${navn}</td><td class="r">${kr(sumG)}</td></tr>` +
      rows.map(l => `<tr><td class="muted">${esc(l.konto)}</td><td>${esc(l.navn)}</td><td class="r">${kr(num(l.ub) * fortegn)}</td></tr>`).join('');
  }).join('');
  return `<section class="card"><div class="card-h"><h2>Kontoer</h2><span class="muted small">Utgående saldo per ${mLabel(d.periode)}. Gjeld, egenkapital og inntekter vises som positive tall.</span></div>
    <div class="tw"><table class="tbl"><tbody>${del}</tbody></table></div></section>`;
}
function sbListeAlle(){ return (S.saldobalanser || []).filter(x => x.periode).sort((a, b) => b.periode.localeCompare(a.periode)); }
function vSaldo(){
  const list = sbListeAlle();
  if (!sbYM || !list.some(x => x.periode === sbYM)) sbYM = list[0]?.periode || null;
  const d = list.find(x => x.periode === sbYM), i = list.indexOf(d), prev = list[i + 1];
  const nyKnapp = (canWrite ? `<label class="btn primary" for="sb-csv" tabindex="0" role="button">Importer CSV</label><input type="file" id="sb-csv" accept=".csv,.txt,.skv,text/csv" hidden>` : '') +
    (canWrite ? `<button class="btn" data-act="new" data-col="saldobalanser" data-def='${esc(JSON.stringify({periode: shiftYM(curYM(), -1)}))}'>Legg inn for hånd</button>` : '');
  if (!d) return head('Økonomi', 'Saldobalanse', SB_TEKST, nyKnapp) +
    empty('Ingen saldobalanser ennå', 'Eksporter saldobalansen fra regnskapssystemet som CSV og trykk «Importer CSV». Portalen fyller ut tallene selv.', '');
  const t = sbTall(d), p = prev ? sbTall(prev) : null;
  const dlt = k => { if (!p) return ''; const v = t[k] - p[k]; return `<div class="s">${v === 0 ? 'Uendret' : (v > 0 ? '+' : '−') + kr(Math.abs(v))} fra ${mShort(prev.periode)}</div>`; };
  const lanPortal = sum(S.eiendommer || [], e => num(e.lan)), avvik = Math.round(t.rest - lanPortal);
  const nav = list.length > 1 ? `<div class="mnav"><button class="iconbtn" data-act="sb-nav" data-d="1" ${i >= list.length - 1 ? 'disabled' : ''} aria-label="Eldre måned">‹</button><b>${mLabel(d.periode)}</b><button class="iconbtn" data-act="sb-nav" data-d="-1" ${i <= 0 ? 'disabled' : ''} aria-label="Nyere måned">›</button></div>` : '';
  return head('Økonomi', 'Saldobalanse', SB_TEKST, nyKnapp) + `
  <section class="card"><div class="card-h"><h2>Saldobalanse ${mLabel(d.periode)}</h2><div class="row">${nav}<button class="btn sm" data-act="edit" data-col="saldobalanser" data-id="${esc(d.id)}">${canWrite ? 'Rediger' : 'Detaljer'}</button></div></div>
    <div class="kpis">
      <div class="kpi hl"><div class="l">Restgjeld bank</div><div class="v">${kr(t.rest)}</div>${dlt('rest')}</div>
      <div class="kpi"><div class="l">Gjeld til oss</div><div class="v">${kr(t.oss)}</div>${dlt('oss')}</div>
      <div class="kpi"><div class="l">Bankinnskudd</div><div class="v">${kr(t.bank)}</div>${dlt('bank')}</div>
      <div class="kpi"><div class="l">Resultat hittil i år</div><div class="v ${negc(t.res)}">${kr(t.res)}</div>${dlt('res')}</div>
    </div>
    <div class="grid2" style="margin-top:18px">
      <div class="tw"><table class="tbl"><tbody>
        <tr><td>Inntekter hittil i år</td><td class="r">${kr(t.inn)}</td></tr>
        <tr><td>Kostnader hittil i år</td><td class="r ${t.kost ? 'neg' : ''}">${t.kost ? '−' : ''}${kr(t.kost)}</td></tr>
        <tr class="sum"><td>Resultat</td><td class="r ${negc(t.res)}">${kr(t.res)}</td></tr></tbody></table></div>
      <div class="tw"><table class="tbl"><tbody>
        <tr><td>Restgjeld i saldobalansen</td><td class="r">${kr(t.rest)}</td></tr>
        <tr><td>Lån registrert i portalen</td><td class="r">${kr(lanPortal)}</td></tr>
        <tr class="sum"><td>Avvik</td><td class="r">${avvik === 0 ? chip('ok', 'Stemmer') : (avvik > 0 ? '+' : '−') + kr(Math.abs(avvik))}</td></tr></tbody></table>
        ${avvik !== 0 && t.rest ? '<p class="hint" style="margin:10px 0 0">Oppdater lånet på hver eiendom under Eiendommer → Rediger, så stemmer økonomitallene.</p>' : ''}</div>
    </div>
    ${d.notat ? `<p class="muted" style="margin:18px 0 0;max-width:75ch">${esc(d.notat)}</p>` : ''}
    ${d.filnavn ? `<p class="muted small" style="margin:14px 0 0">Importert fra ${esc(d.filnavn)}</p>` : ''}
  </section>
  ${sbKontoer(d)}
  ${list.length > 1 ? `<section class="card"><div class="card-h"><h2>Utvikling</h2></div>
    <div class="tw"><table class="tbl"><thead><tr><th>Måned</th><th class="r">Restgjeld</th><th class="r">Gjeld til oss</th><th class="r">Bank</th><th class="r">Resultat hittil</th></tr></thead><tbody>
    ${list.map(x => { const q = sbTall(x); return `<tr class="click ${x.periode === sbYM ? 'em' : ''}" data-act="sb-vis" data-ym="${esc(x.periode)}"><td>${mLabel(x.periode)}</td><td class="r">${kr(q.rest)}</td><td class="r">${kr(q.oss)}</td><td class="r">${kr(q.bank)}</td><td class="r ${negc(q.res)}">${kr(q.res)}</td></tr>`; }).join('')}
    </tbody></table></div></section>` : ''}`;
}

/* ---------- eiere og tilgang ---------- */
const ROLLE = { admin: 'Administrator', skriv: 'Kan endre', les: 'Kan se' };
let brukere = [], sisteLenke = null;
async function hentBrukere(){ try { brukere = (await api('/api/users')).brukere || []; } catch { brukere = []; } }
function vEiere(){
  const admin = me?.rolle === 'admin';
  const lenkeKort = sisteLenke ? `<section class="card"><div class="card-h"><h2>Lenke til ${esc(sisteLenke.navn)}</h2></div>
    <p class="muted" style="margin:0 0 12px">Send lenken til ${esc(sisteLenke.navn)} på e-post eller SMS. Den gjelder i ${sisteLenke.dager} dager og kan bare brukes én gang. Der velger ${esc(sisteLenke.navn)} sitt eget passord.</p>
    <div class="copy"><input class="inp" id="lenke" readonly value="${esc(sisteLenke.url)}"><button class="btn primary" data-act="kopier">Kopier</button></div></section>` : '';
  return head('Selskapet', 'Eiere og tilgang', admin ? 'Inviter eierne og bestem hva hver enkelt kan gjøre. Alle logger inn med e-post og eget passord.' : 'Hvem som har tilgang til portalen.',
      admin ? `<button class="btn primary" data-act="inviter">Inviter eier</button>` : '') + lenkeKort + `
  <section class="card">${brukere.length ? `<div class="tw"><table class="tbl"><thead><tr><th>Navn</th>${admin ? '<th>E-post</th>' : ''}<th>Tilgang</th>${admin ? '<th>Status</th><th></th>' : ''}</tr></thead><tbody>
    ${brukere.map(b => `<tr><td><b>${esc(b.navn)}</b>${b.id === me?.id ? ' <span class="muted small">(deg)</span>' : ''}</td>${admin ? `<td>${esc(b.epost)}</td>` : ''}
      <td>${admin && b.id !== me?.id ? `<select class="inp" style="padding:6px 10px;width:auto" data-rolle="${esc(b.id)}">${Object.entries(ROLLE).map(([k, v]) => `<option value="${k}" ${b.rolle === k ? 'selected' : ''}>${v}</option>`).join('')}</select>` : esc(ROLLE[b.rolle] || b.rolle)}</td>
      ${admin ? `<td>${b.aktiv ? chip('ok', 'Aktiv') : b.invitert ? chip('warn', 'Invitert') : chip('nodot', 'Lenken har gått ut')}</td>
      <td class="r">${b.id !== me?.id ? `<button class="btn sm" data-act="ny-lenke" data-id="${esc(b.id)}" data-navn="${esc(b.navn)}">${b.aktiv ? 'Nytt passord' : 'Ny lenke'}</button> <button class="btn sm danger" data-act="fjern" data-id="${esc(b.id)}">Fjern</button>` : ''}</td>` : ''}</tr>`).join('')}
  </tbody></table></div>` : empty('Ingen eiere', '')}</section>
  ${admin ? `<p class="muted small" style="margin:0"><b>Administrator</b> kan alt, også invitere og fjerne eiere. <b>Kan endre</b> kan registrere innbetalinger, gjøremål og tall. <b>Kan se</b> kan bare lese. Glemmer noen passordet, trykker du «Nytt passord» og sender den nye lenken.</p>` : ''}`;
}
function openInviter(){
  $('#modal').innerHTML = `<form id="iform" novalidate><div class="mh"><h2>Inviter eier</h2><button type="button" class="x" data-act="close" aria-label="Lukk">×</button></div>
    <div class="fgrid"><label class="fld"><span class="lab">Navn</span><input id="i_navn" class="inp" autocomplete="off"></label>
    <label class="fld"><span class="lab">E-post</span><input id="i_epost" class="inp" type="email" autocomplete="off"></label>
    <label class="fld full"><span class="lab">Tilgang</span><select id="i_rolle" class="inp">${Object.entries(ROLLE).map(([k, v]) => `<option value="${k}" ${k === 'skriv' ? 'selected' : ''}>${v}</option>`).join('')}</select></label></div>
    <div class="ferr" id="ferr" hidden></div>
    <div class="mf"><span class="sp"></span><button type="button" class="btn" data-act="close">Avbryt</button><button class="btn primary" type="submit">Lag invitasjon</button></div></form>`;
  M = {col: null}; $('#mb').hidden = false; $('#i_navn').focus();
  $('#iform').addEventListener('submit', async e => {
    e.preventDefault();
    const navn = $('#i_navn').value.trim(), epost = $('#i_epost').value.trim(), rolle = $('#i_rolle').value;
    try { const r = await api('/api/users', {action: 'inviter', navn, epost, rolle});
      sisteLenke = {navn, url: location.origin + r.lenke, dager: r.dager}; closeModal(); await hentBrukere(); render(); }
    catch (er){ const fe = $('#ferr'); fe.textContent = er.message; fe.hidden = false; }
  });
}
function openPassord(){
  $('#modal').innerHTML = `<form id="pform" novalidate><div class="mh"><h2>Bytt passord</h2><button type="button" class="x" data-act="close" aria-label="Lukk">×</button></div>
    <div class="fgrid"><label class="fld full"><span class="lab">Nåværende passord</span><input id="p_g" class="inp" type="password" autocomplete="current-password"></label>
    <label class="fld full"><span class="lab">Nytt passord</span><input id="p_n" class="inp" type="password" autocomplete="new-password"><span class="hint">Minst 10 tegn</span></label></div>
    <div class="ferr" id="ferr" hidden></div>
    <div class="mf"><span class="sp"></span><button type="button" class="btn" data-act="close">Avbryt</button><button class="btn primary" type="submit">Lagre</button></div></form>`;
  M = {col: null}; $('#mb').hidden = false; $('#p_g').focus();
  $('#pform').addEventListener('submit', async e => {
    e.preventDefault();
    try { await api('/api/auth', {action: 'bytt-passord', gammelt: $('#p_g').value, nytt: $('#p_n').value}); closeModal(); toast('Passordet er byttet'); }
    catch (er){ const fe = $('#ferr'); fe.textContent = er.message; fe.hidden = false; }
  });
}

''')

# ---------- ruting ----------
rep("forsikringer:vForsikringer };", "forsikringer:vForsikringer, eiere:vEiere };")
rep("  {h:'forsikringer', t:'Forsikringer', i:'shield', b:() => S.forsikringer?.filter(forsMangler).length},\n];",
    "  {h:'forsikringer', t:'Forsikringer', i:'shield', b:() => S.forsikringer?.filter(forsMangler).length},\n  {g:'Selskapet'},\n  {h:'eiere', t:'Eiere og tilgang', i:'people'},\n];")

# ---------- «meg» nederst i menyen ----------
cut('function renderMe(){', 'let raf = 0;', '''function renderMe(){
  if (!me){ $('#me').innerHTML = ''; return; }
  $('#me').innerHTML = `<img alt="" src="${esc(me.avatarUrl)}"><div style="min-width:0"><b></b><span>${esc(ROLLE[me.rolle] || '')}</span>
    <div class="acts"><button class="linkbtn" data-act="passord">Bytt passord</button><button class="linkbtn" data-act="loggut">Logg ut</button></div></div>`;
  $('#me b').textContent = me.name || 'Deg';
}
''')
rep('''  if (offline) html = `<div class="note-bar">Dette er en forhåndsvisning uten tilkobling. Åpne portalen på claude.ai for å se og lagre data.</div>` + html;
  else if (!canWrite) html = `<div class="note-bar">Du har lesetilgang. Be eieren av portalen gi deg tilgang som bidragsyter for å kunne endre.</div>` + html;''',
    '''  if (offline) html = `<div class="note-bar">Mistet forbindelsen til serveren. Last siden på nytt.</div>` + html;
  else if (!canWrite) html = `<div class="note-bar">Du kan se alt, men ikke endre. Be en administrator om å gi deg tilgangen «Kan endre».</div>` + html;''')

# ---------- hendelser for saldobalanse og eiere ----------
cut("  if (a === 'sb-run') return sbAnalyser();", "  if (a === 'toggle'){", '''  if (a === 'sb-vis'){ sbYM = t.dataset.ym; render(); window.scrollTo(0, 0); return; }
  if (a === 'sb-nav'){ const L = sbListeAlle(), i = L.findIndex(x => x.periode === sbYM) + (+t.dataset.d); if (L[i]){ sbYM = L[i].periode; render(); } return; }
  if (a === 'inviter') return openInviter();
  if (a === 'passord') return openPassord();
  if (a === 'loggut'){ try { await api('/api/auth', {action: 'logout'}); } catch {} location.href = '/'; return; }
  if (a === 'kopier'){ const i = $('#lenke'); i.select(); try { await navigator.clipboard.writeText(i.value); toast('Lenken er kopiert'); } catch { document.execCommand('copy'); toast('Lenken er kopiert'); } return; }
  if (a === 'ny-lenke'){ try { const r = await api('/api/users', {action: 'ny-lenke', id: t.dataset.id}); sisteLenke = {navn: t.dataset.navn, url: location.origin + r.lenke, dager: r.dager}; await hentBrukere(); render(); window.scrollTo(0, 0); } catch (e){ toast(e.message, true); } return; }
  if (a === 'fjern'){
    if (t.dataset.armed !== '1'){ t.dataset.armed = '1'; t.classList.add('armed'); t.textContent = 'Trykk igjen'; return; }
    try { await api('/api/users', {action: 'fjern', id: t.dataset.id}); await hentBrukere(); render(); toast('Fjernet'); } catch (e){ toast(e.message, true); } return;
  }
''')
cut("document.addEventListener('change', ev => {", "$('#mb').addEventListener('click'", '''document.addEventListener('change', async ev => {
  if (ev.target.id === 'sb-csv'){ const f = ev.target.files?.[0]; ev.target.value = ''; return sbImporter(f); }
  const id = ev.target.dataset?.rolle; if (!id) return;
  try { await api('/api/users', {action: 'rolle', id, rolle: ev.target.value}); await hentBrukere(); toast('Tilgangen er endret'); } catch (e){ toast(e.message, true); render(); }
});
''')

# ---------- oppstart: eget API i stedet for Claude ----------
cut('/* ---------- oppstart ---------- */', '</script>', r'''/* ---------- API og innlogging ---------- */
async function api(url, data){
  const r = await fetch(url, data ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data), credentials: 'same-origin'} : {credentials: 'same-origin'});
  let j = {}; try { j = await r.json(); } catch {}
  if (r.status === 401 && url !== '/api/auth'){ location.reload(); throw new Error('Logget ut'); }
  if (!r.ok) throw Object.assign(new Error(j.melding || 'Noe gikk galt. Prøv igjen.'), {code: j.error});
  return j;
}
async function lastData(){
  try { const r = await api('/api/data'); COLS.forEach(c => S[c] = r.data[c] || []); offline = false; }
  catch { offline = true; COLS.forEach(c => { if (S[c] === null) S[c] = []; }); }
  render();
}
/* samme grensesnitt som den gamle databasen, så resten av koden er uendret */
db = { collection: c => ({
  add: async data => { const r = await api('/api/data', {op: 'add', col: c, data}); await lastData(); return r; },
  doc: id => ({
    set: async data => { await api('/api/data', {op: 'set', col: c, id, data}); await lastData(); },
    update: async data => { await api('/api/data', {op: 'update', col: c, id, data}); await lastData(); },
    delete: async () => { await api('/api/data', {op: 'delete', col: c, id}); await lastData(); }
  })
})};
const avatar = navn => { const ini = (navn || '?').split(/\s+/).map(w => w[0] || '').join('').slice(0, 2).toUpperCase();
  return 'data:image/svg+xml,' + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="72" height="72"><rect width="72" height="72" rx="36" fill="#9C6A1C"/><text x="36" y="45" font-family="Arial" font-size="28" font-weight="700" fill="#fff" text-anchor="middle">${ini.replace(/[<&>]/g, '')}</text></svg>`); };
user = {
  profiles: async ids => Object.fromEntries(ids.map(id => { const b = brukere.find(x => x.id === id); return [id, b ? {name: b.navn} : null]; })),
  search: async q => brukere.filter(b => !q || b.navn.toLowerCase().includes(q.toLowerCase())).map(b => ({id: b.id, name: b.navn, avatarUrl: avatar(b.navn), isMe: b.id === me?.id}))
};

function authSide(innhold){
  document.querySelector('.app').hidden = true;
  let w = $('#auth'); if (!w){ w = document.createElement('div'); w.id = 'auth'; w.className = 'auth'; document.body.prepend(w); }
  w.innerHTML = `<div class="card"><div class="brand"><span>LV</span><span class="bar"></span><span>EIENDOM AS</span></div>${innhold}</div>`;
  return w;
}
function feltErr(w, msg){ const e = w.querySelector('.ferr'); e.textContent = msg; e.hidden = false; }
function visLogin(harBrukere){
  if (!harBrukere) return visOppstart();
  const w = authSide(`<h2 style="margin-bottom:6px">Eierportal</h2><p>Logg inn med e-post og passord.</p>
    <form id="lf" novalidate><label class="fld"><span class="lab">E-post</span><input id="l_e" class="inp" type="email" autocomplete="username" required></label>
    <label class="fld"><span class="lab">Passord</span><input id="l_p" class="inp" type="password" autocomplete="current-password" required></label>
    <div class="ferr" hidden></div><button class="btn primary" type="submit">Logg inn</button>
    <p class="small" style="margin-top:8px">Glemt passordet? Be en administrator om en ny lenke.</p></form>`);
  $('#l_e').focus();
  $('#lf').addEventListener('submit', async e => { e.preventDefault();
    try { await api('/api/auth', {action: 'login', epost: $('#l_e').value, passord: $('#l_p').value}); location.reload(); }
    catch (er){ feltErr(w, er.message); } });
}
function visOppstart(){
  const w = authSide(`<h2 style="margin-bottom:6px">Sett opp portalen</h2><p>Opprett den første administratoren. Du trenger oppstartskoden.</p>
    <form id="of" novalidate><label class="fld"><span class="lab">Navn</span><input id="o_n" class="inp" autocomplete="name"></label>
    <label class="fld"><span class="lab">E-post</span><input id="o_e" class="inp" type="email" autocomplete="username"></label>
    <label class="fld"><span class="lab">Passord</span><input id="o_p" class="inp" type="password" autocomplete="new-password"><span class="hint">Minst 10 tegn</span></label>
    <label class="fld"><span class="lab">Oppstartskode</span><input id="o_k" class="inp" autocomplete="off"></label>
    <div class="ferr" hidden></div><button class="btn primary" type="submit">Opprett og logg inn</button></form>`);
  $('#of').addEventListener('submit', async e => { e.preventDefault();
    try { await api('/api/auth', {action: 'oppstart', navn: $('#o_n').value, epost: $('#o_e').value, passord: $('#o_p').value, kode: $('#o_k').value}); location.href = '/'; }
    catch (er){ feltErr(w, er.message); } });
}
async function visInvitasjon(token){
  let info;
  try { info = await api('/api/auth', {action: 'invitasjon-info', token}); }
  catch (er){ authSide(`<h2 style="margin-bottom:6px">Lenken virker ikke</h2><p>${esc(er.message)}</p><a class="btn" href="/">Til innlogging</a>`); return; }
  const w = authSide(`<h2 style="margin-bottom:6px">Velkommen, ${esc(info.navn)}</h2><p>Velg et passord for ${esc(info.epost)}.</p>
    <form id="vf" novalidate><input type="email" autocomplete="username" value="${esc(info.epost)}" hidden>
    <label class="fld"><span class="lab">Passord</span><input id="v_p" class="inp" type="password" autocomplete="new-password"><span class="hint">Minst 10 tegn</span></label>
    <label class="fld"><span class="lab">Gjenta passordet</span><input id="v_p2" class="inp" type="password" autocomplete="new-password"></label>
    <div class="ferr" hidden></div><button class="btn primary" type="submit">Lagre og logg inn</button></form>`);
  $('#v_p').focus();
  $('#vf').addEventListener('submit', async e => { e.preventDefault();
    if ($('#v_p').value !== $('#v_p2').value) return feltErr(w, 'Passordene er ikke like.');
    try { await api('/api/auth', {action: 'invitasjon', token, passord: $('#v_p').value}); location.href = '/'; }
    catch (er){ feltErr(w, er.message); } });
}

(async function init(){
  const inv = new URLSearchParams(location.search).get('invitasjon');
  if (inv){ history.replaceState(null, '', '/'); return visInvitasjon(inv); }
  let a;
  try { a = await api('/api/auth'); }
  catch { authSide('<h2>Får ikke kontakt med serveren</h2><p>Prøv igjen om litt.</p>'); return; }
  if (!a.bruker) return visLogin(a.harBrukere);
  me = {id: a.bruker.id, name: a.bruker.navn, rolle: a.bruker.rolle, avatarUrl: avatar(a.bruker.navn), isOwner: a.bruker.rolle === 'admin'};
  canWrite = a.bruker.rolle === 'admin' || a.bruker.rolle === 'skriv';
  render();
  await hentBrukere();
  renderMe();
  await lastData();
  setInterval(() => { if (document.visibilityState === 'visible' && !M) lastData(); }, 30000);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && !M) lastData(); });
})();
''')

s = s.replace("document.addEventListener('keydown', e => { if (e.key === 'Escape' && M) closeModal(); });",
  "document.addEventListener('keydown', e => { if (e.key === 'Escape' && M) closeModal(); if ((e.key === 'Enter' || e.key === ' ') && e.target.getAttribute?.('for') === 'sb-csv'){ e.preventDefault(); $('#sb-csv').click(); } });")
assert 'claude.use' not in s and 'sample.json' not in s
(P / 'index.html').write_text(s)
print('ok', len(s))
