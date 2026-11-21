import {createHighlighter} from 'shiki';
import fs from 'node:fs';
const root=process.argv[2];
if(!root) throw new Error('Pass the absolute Grotto repository path.');
const out=root+'/out/summer-memories/theme-comparison';fs.mkdirSync(out,{recursive:true});
const local=JSON.parse(fs.readFileSync(root+'/out/summer-memories/vscode-preview/themes/pergola-day.json','utf8'));local.name='grotto-pergola-day';local.type='light';
const themes=['grotto-pergola-day','catppuccin-latte','github-light-default','light-plus','solarized-light'];
const labels=['Grotto Pergola Day','Catppuccin Latte','GitHub Light Default','VS Code Light+','Solarized Light'];
const samples=JSON.parse(fs.readFileSync(out+'/samples.json','utf8'));
const h=await createHighlighter({themes:[local,...themes.slice(1)],langs:Object.keys(samples)});
let body='<h1>Grotto beside established light themes</h1><p>The same code, font and TextMate grammars, using Shiki 4.4.3 theme snapshots. These are browser renders of theme rules; semantic highlighting and editor UI are outside this comparison.</p><label>Language <select id="language">'+Object.keys(samples).map(x=>`<option>${x}</option>`).join('')+'</select></label>';
const evidence={shiki:'4.4.3',themes:{}};
for(const [lang,code] of Object.entries(samples)){
 body+=`<section data-language="${lang}" ${lang==='typescript'?'':'hidden'}>`;
 for(let i=0;i<themes.length;i++){
  const t=themes[i];const tok=h.codeToTokens(code,{lang,theme:t});
  evidence.themes[t]??={label:labels[i],languages:{}};
  const counts={};for(const line of tok.tokens)for(const token of line){const n=token.content.replace(/\s/g,'').length;if(n){const color=token.color??tok.fg;counts[color]=(counts[color]??0)+n;}}
  evidence.themes[t].languages[lang]={bg:tok.bg,fg:tok.fg,counts};
  body+=`<article><h2>${labels[i]}</h2>`+h.codeToHtml(code,{lang,theme:t})+'</article>';
 }
 body+='</section>';
}
const css='body{margin:24px;background:#e4e4e4;color:#222;font:16px/1.5 system-ui}p{max-width:95ch}section{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}section[hidden]{display:none}h2{font-size:16px;margin:0;padding:10px;background:#d8d8d8}pre{margin:0;padding:16px;overflow:auto;font:13px/1.65 "DejaVu Sans Mono",monospace;min-height:490px}article{min-width:0}select{font:inherit;margin-bottom:18px}@media(max-width:850px){section{grid-template-columns:minmax(0,1fr)}}';
fs.writeFileSync(out+'/comparison.html','<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Grotto and established light themes</title><style>'+css+'</style><body>'+body+'<script>document.querySelector("select").onchange=e=>document.querySelectorAll("section").forEach(x=>x.hidden=x.dataset.language!==e.target.value)</script></body></html>');
fs.writeFileSync(out+'/token-colors.json',JSON.stringify(evidence,null,2)+'\n');
h.dispose();
