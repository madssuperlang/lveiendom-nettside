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
rep('<!doctype html><html><head>', '<!doctype html><html lang="nb"><head><title>LV Eiendom – eierportal</title><meta name="robots" content="noindex,nofollow">')
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
function sbListeAlle(){ return (S.saldobalanser || []).filter(x => x.periode).sort((a, b) => b.periode.localeCompare(a.periode)); }
function vSaldo(){
  const list = sbListeAlle();
  if (!sbYM || !list.some(x => x.periode === sbYM)) sbYM = list[0]?.periode || null;
  const d = list.find(x => x.periode === sbYM), i = list.indexOf(d), prev = list[i + 1];
  const nyKnapp = addBtn('saldobalanser', 'Legg inn måned', `data-def='${esc(JSON.stringify({periode: shiftYM(curYM(), -1)}))}'`);
  if (!d) return head('Økonomi', 'Saldobalanse', 'Tallene fra saldobalansen hver måned: restgjeld, gjeld til eierne, bank og resultat. Hent tallene fra regnskapet og legg dem inn her.', nyKnapp) +
    empty('Ingen saldobalanser ennå', 'Be regnskapsføreren om saldobalansen for forrige måned, og legg inn de viktigste tallene.', nyKnapp);
  const t = sbTall(d), p = prev ? sbTall(prev) : null;
  const dlt = k => { if (!p) return ''; const v = t[k] - p[k]; return `<div class="s">${v === 0 ? 'Uendret' : (v > 0 ? '+' : '−') + kr(Math.abs(v))} fra ${mShort(prev.periode)}</div>`; };
  const lanPortal = sum(S.eiendommer || [], e => num(e.lan)), avvik = Math.round(t.rest - lanPortal);
  const nav = list.length > 1 ? `<div class="mnav"><button class="iconbtn" data-act="sb-nav" data-d="1" ${i >= list.length - 1 ? 'disabled' : ''} aria-label="Eldre måned">‹</button><b>${mLabel(d.periode)}</b><button class="iconbtn" data-act="sb-nav" data-d="-1" ${i <= 0 ? 'disabled' : ''} aria-label="Nyere måned">›</button></div>` : '';
  return head('Økonomi', 'Saldobalanse', 'Tallene fra saldobalansen hver måned: restgjeld, gjeld til eierne, bank og resultat. Hent tallene fra regnskapet og legg dem inn her.', nyKnapp) + `
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
  </section>
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

assert 'claude.use' not in s and 'sample.json' not in s
(P / 'index.html').write_text(s)
print('ok', len(s))
