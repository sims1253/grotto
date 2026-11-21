// Install shiki@4.4.3 in a temporary Node project and copy this script there.
// Run: node study_preview.mjs /absolute/path/to/grotto
import {createHighlighter} from 'shiki';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
const root=process.argv[2];
if(!root) throw new Error('Pass the absolute Grotto repository path.');
const out=path.join(root,'out/grotto-studies');
const samples=JSON.parse(fs.readFileSync(path.join(out,'samples.json'),'utf8'));
const profiles=JSON.parse(fs.readFileSync(path.join(out,'profiles.json'),'utf8'));
const descriptions={...profiles,pergola:'The previous Pergola, for comparison.'};
const names=Object.keys(descriptions);
const titleCase=s=>s[0].toUpperCase()+s.slice(1);
const escape=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const themes=[],inputs={};
for(const name of names)for(const variant of ['day','night']){
 const rel=`out/${name==='pergola'?'summer-memories':'grotto-studies'}/vscode-preview/themes/${name}-${variant}.json`;
 const contents=fs.readFileSync(path.join(root,rel));inputs[rel]=crypto.createHash('sha256').update(contents).digest('hex');
 const theme=JSON.parse(contents);theme.name=name+'-'+variant;theme.type=variant==='day'?'light':'dark';themes.push(theme);
}
const h=await createHighlighter({themes,langs:Object.keys(samples)});
const options=names.map(x=>`<option value="${x}">${titleCase(x)}</option>`).join('');
let body=`<header><h1>Grotto studies</h1><p>Four ways to put color beneath the vines. Browse the set, then compare any two at the same size.</p></header>
<nav aria-label="Palette comparison"><label>Light <select id="variant"><option value="day">Day</option><option value="night">Night</option></select></label>
<label>Code <select id="language">${Object.keys(samples).map(x=>`<option value="${x}">${x==='r'?'R':titleCase(x)}</option>`).join('')}</select></label>
<label>Layout <select id="layout"><option value="all">All four</option><option value="pair">Compare two</option></select></label>
<label>Left <select id="left" disabled>${options}</select></label><label>Right <select id="right" disabled>${options}</select></label></nav><main class="grid">`;
const evidence={shiki:'4.4.3',themes:{}};
for(const theme of themes){
 const variant=theme.type==='light'?'day':'night';const name=theme.name.replace(/-(day|night)$/,'');
 evidence.themes[theme.name]={};
 for(const [lang,code] of Object.entries(samples)){
  const tok=h.codeToTokens(code,{lang,theme:theme.name});const counts={};
  for(const line of tok.tokens)for(const token of line){const n=token.content.replace(/\s/g,'').length;if(n){const c=token.color??tok.fg;counts[c]=(counts[c]??0)+n;}}
  evidence.themes[theme.name][lang]={bg:tok.bg,counts};
  body+=`<article data-name="${name}" data-variant="${variant}" data-language="${lang}" hidden><header><h2>${titleCase(name)} ${titleCase(variant)}</h2><p>${escape(descriptions[name])}</p></header>`+h.codeToHtml(code,{lang,theme:theme.name})+'</article>';
 }
}
body+='</main><footer><p>Browser renders from actual theme rules using Shiki 4.4.3. Editor semantic highlighting can change which tokens receive color.</p><p><a href="README.md">Install and review notes</a> · <a href="role-specimens.html">Selections, diagnostics and color-vision simulations</a> · <a href="../summer-memories/comparison.html">Pergola and Stone</a> · <a href="../next-generation/comparison.html">Cove, Grove and Dusk</a></p></footer>';
const css=`:root{font-family:'DejaVu Sans',sans-serif;color:#283039;background:#e6e8e9;color-scheme:light}body{margin:0;padding:28px clamp(16px,3vw,52px)}header>p,footer p{max-width:76ch;line-height:1.55}h1{font-size:30px;font-weight:600;letter-spacing:-.5px;margin:0}h2{font-size:18px;margin:0}nav{display:flex;align-items:end;gap:16px;flex-wrap:wrap;margin:24px 0}label{display:grid;gap:5px;font-size:14px}select{font:inherit;color:inherit;border:1px solid #87929b;border-radius:4px;background:#f8fafb;padding:8px 30px 8px 9px}select:disabled{opacity:.5}a{color:#254e79}a:focus-visible,select:focus-visible{outline:3px solid #254e79;outline-offset:3px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}article{min-width:0}article[hidden]{display:none}article>header{padding:12px 16px;background:#d7dde0}article>header p{margin:5px 0 0;font-size:13px}pre{font:13px/1.65 'DejaVu Sans Mono',monospace;padding:18px;margin:0;overflow:auto;min-height:480px}footer{font-size:13px;margin-top:28px}@media(max-width:850px){.grid{grid-template-columns:minmax(0,1fr)}pre{min-height:0}body{padding:20px 14px}nav{gap:10px}}`;
const js=`const controls=Object.fromEntries(['variant','language','layout','left','right'].map(id=>[id,document.getElementById(id)]));controls.right.value='fig';function render(){const pair=controls.layout.value==='pair';controls.left.disabled=controls.right.disabled=!pair;document.querySelectorAll('article').forEach(a=>{const active=a.dataset.variant===controls.variant.value&&a.dataset.language===controls.language.value;const chosen=pair?[controls.left.value,controls.right.value].includes(a.dataset.name):a.dataset.name!=='pergola';a.hidden=!(active&&chosen);a.style.order=pair?(a.dataset.name===controls.left.value?0:1):0;});}Object.values(controls).forEach(c=>c.addEventListener('change',render));render();`;
fs.writeFileSync(path.join(out,'comparison.html'),'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Grotto studies</title><style>'+css+'</style><body>'+body+'<script>'+js+'</script></body></html>');
fs.writeFileSync(path.join(out,'token-colors.json'),JSON.stringify(evidence,null,2)+'\n');
fs.writeFileSync(path.join(out,'preview-inputs.json'),JSON.stringify({shiki:'4.4.3',sha256:inputs},null,2)+'\n');
h.dispose();
