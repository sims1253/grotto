// Copy into a temporary Node project with shiki@4.4.3 installed.
// Run: node vivid_preview.mjs /absolute/path/to/grotto
import {createHighlighter} from 'shiki';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
const root=process.argv[2];if(!root)throw new Error('Pass the absolute repository path.');
const out=root+'/out/vivid-studies';
const samples=JSON.parse(fs.readFileSync(out+'/samples.json','utf8'));
const locals=[], inputHashes={};
for(const profile of ['fig','rainstone'])for(const vivid of [false,true])for(const variant of ['day','night']){
 const name=profile+(vivid?'-vivid':'')+'-'+variant;
 const rel=`out/${vivid?'vivid-studies':'grotto-studies'}/vscode-preview/themes/${name}.json`;
 const bytes=fs.readFileSync(`${root}/${rel}`);inputHashes[rel]=crypto.createHash('sha256').update(bytes).digest('hex');
 const theme=JSON.parse(bytes);
 theme.name=name;theme.type=variant==='day'?'light':'dark';locals.push(theme);
}
const refs={day:['catppuccin-latte','light-plus'],night:['catppuccin-mocha','dark-plus']};
const h=await createHighlighter({themes:[...locals,...Object.values(refs).flat()],langs:Object.keys(samples)});
let body='<h1>Grotto: a bolder comparison</h1><p>Left: the earlier studies. Right: colored variables and comments, stronger accents, and lighter Day selection fills. Reference themes follow below.</p><p>All versions use the same font, source code and TextMate grammars. The bolder versions retain the configured text contrast floors.</p><nav><label>Light <select id="variant"><option>day</option><option>night</option></select></label> <label>Code <select id="language">'+Object.keys(samples).map(x=>`<option>${x}</option>`).join('')+'</select></label></nav>';
const evidence={shiki:'4.4.3',themes:{}};
for(const variant of ['day','night'])for(const [lang,code] of Object.entries(samples)){
 const choices=[['fig-'+variant,'Fig before'],['fig-vivid-'+variant,'Fig Vivid'],['rainstone-'+variant,'Rainstone before'],['rainstone-vivid-'+variant,'Rainstone Vivid'],[refs[variant][0],variant==='day'?'Catppuccin Latte':'Catppuccin Mocha'],[refs[variant][1],variant==='day'?'VS Code Light+':'VS Code Dark+']];
 body+=`<section data-variant="${variant}" data-language="${lang}" hidden>`;
 for(const [theme,label] of choices){
  const tok=h.codeToTokens(code,{lang,theme});const counts={};
  for(const row of tok.tokens)for(const t of row){const n=t.content.replace(/\s/g,'').length;if(n)counts[t.color]=(counts[t.color]??0)+n;}
  evidence.themes[theme]??={};evidence.themes[theme][lang]={bg:tok.bg,counts};
  body+=`<article data-theme="${theme}"><h2>${label}</h2>`+h.codeToHtml(code,{lang,theme})+'</article>';
 }
 body+='</section>';
}
body+='<footer><p>Browser renders with Shiki 4.4.3; editor semantic highlighting can change token assignments.</p><p><a href="README.md">Install and review notes</a> · <a href="role-specimens.html">State previews and color-vision simulations</a> · <a href="../grotto-studies/comparison.html">Earlier studies</a></p></footer>';
const css=`body{margin:24px;background:#e6e8e9;color:#283039;font:16px/1.5 'DejaVu Sans',sans-serif}p{max-width:80ch}h1{font-size:28px}h2{font-size:17px;margin:0;padding:12px 16px;background:#d7dde0}nav{display:flex;gap:20px;margin-bottom:20px}select{font:inherit;padding:7px}select:focus-visible,a:focus-visible{outline:3px solid #254e79;outline-offset:3px}a{color:#254e79}section{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}section[hidden]{display:none}article{min-width:0}pre{font:13px/1.65 'DejaVu Sans Mono',monospace;margin:0;padding:18px;min-height:450px;overflow:auto}footer{font-size:13px}@media(max-width:850px){section{grid-template-columns:minmax(0,1fr)}pre{min-height:0}}`;
const js=`const v=document.getElementById('variant'),l=document.getElementById('language');function render(){document.querySelectorAll('section').forEach(s=>s.hidden=s.dataset.variant!==v.value||s.dataset.language!==l.value);}v.onchange=l.onchange=render;render();`;
fs.writeFileSync(out+'/comparison.html','<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Grotto vivid comparison</title><style>'+css+'</style><body>'+body+'<script>'+js+'</script></body></html>');
fs.writeFileSync(out+'/token-colors.json',JSON.stringify(evidence,null,2)+'\n');
fs.writeFileSync(out+'/preview-inputs.json',JSON.stringify({shiki:'4.4.3',sha256:inputHashes},null,2)+'\n');
// Check real grammar behavior: broad variable fallbacks must not recolor calls.
for(const t of locals.filter(t=>t.name.includes('-vivid-')))for(const [lang,code] of Object.entries({r:'acc <- rolling_mean(values)',typescript:'let acc = rolling_mean(values);',python:'acc = rolling_mean(values)'})){
 const tokens=h.codeToTokens(code,{lang,theme:t.name}).tokens.flat();
 assert.equal(tokens.find(x=>x.content.trim()==='acc')?.color.toLowerCase(),t.semanticTokenColors.variable.foreground,`${t.name} ${lang}: variable color`);
 assert.equal(tokens.find(x=>x.content==='rolling_mean')?.color.toLowerCase(),t.semanticTokenColors.function.foreground,`${t.name} ${lang}: function color`);
}
h.dispose();
