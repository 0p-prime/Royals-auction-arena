(function(){
'use strict';
var NAME='Ask Pitch AI',history=[],busy=false;
var chips=['Explain every factor on this site','What is uplift?','How does the pressure situation work?','Why do some players have wide intervals?','Who is in the batting top 10?','How are bowlers ranked?'];
function el(t,c,x){var e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e;}
var fab=el('button','ai-fab');fab.type='button';fab.setAttribute('aria-label','Open '+NAME);fab.setAttribute('aria-expanded','false');
fab.innerHTML='<span class="ai-bot-label">Ask Pitch AI</span><span class="ai-bot-character"><svg viewBox="0 0 88 100" aria-hidden="true" fill="none"><ellipse class="ai-bot-shadow" cx="44" cy="94" rx="23" ry="4" fill="#192963" opacity=".14"/><g class="ai-bot-float"><path d="M44 12V5" stroke="#192963" stroke-width="3" stroke-linecap="round"/><circle cx="44" cy="5" r="4" fill="#e30078"/><path d="M24 64c0-12 40-12 40 0v10c0 9-9 15-20 15s-20-6-20-15V64Z" fill="#fff" stroke="#192963" stroke-width="2.5"/><path d="M18 62 9 72M70 62l9 10" stroke="#e30078" stroke-width="7" stroke-linecap="round"/><rect x="13" y="15" width="62" height="51" rx="21" fill="#fff" stroke="#192963" stroke-width="2.5"/><rect x="21" y="25" width="46" height="29" rx="13" fill="#192963"/><ellipse class="ai-bot-eye" cx="34" cy="38" rx="4" ry="5" fill="#ff86bf"/><ellipse class="ai-bot-eye" cx="54" cy="38" rx="4" ry="5" fill="#ff86bf"/><path d="M39 47q5 4 10 0" stroke="#fff" stroke-width="2" stroke-linecap="round"/><path d="m44 69-4 6h5l-1 7 7-10h-6l1-3Z" fill="#e30078"/></g></svg></span>';
var panel=el('section','ai-panel');panel.hidden=true;panel.setAttribute('role','dialog');panel.setAttribute('aria-label',NAME);
var head=el('div','ai-head');var ttl=el('div','ai-title');ttl.appendChild(el('strong',null,NAME));ttl.appendChild(el('small',null,'Players, rankings and stats'));
var close=el('button','ai-close','\u00d7');close.type='button';close.setAttribute('aria-label','Close assistant');head.appendChild(ttl);head.appendChild(close);
var log=el('div','ai-log');log.setAttribute('aria-live','polite');
var chipBox=el('div','ai-chips');
var form=el('form','ai-form');var input=el('textarea','ai-input');input.rows=1;input.maxLength=600;input.placeholder='Ask a question\u2026';input.setAttribute('aria-label','Your question');
var send=el('button','ai-send','Send');send.type='submit';form.appendChild(input);form.appendChild(send);
var foot=el('div','ai-foot');foot.appendChild(el('span','ai-scope','Ask Pitch AI about players, rankings and stats.'));
var privacy=el('details','ai-privacy');var privacyToggle=el('summary',null,'Privacy');
privacy.appendChild(privacyToggle);
var privacyBody=el('div','ai-privacy-body');privacyBody.appendChild(el('strong',null,'Your questions and Google Gemini'));
privacyBody.appendChild(el('p',null,'Pitch sends your questions and recent messages in this chat to Google Gemini to generate answers. This site uses the Gemini API free tier, so Google may use this content to improve its products.'));
privacyBody.appendChild(el('p',null,'Do not include personal or sensitive information.'));
privacy.appendChild(privacyBody);foot.appendChild(privacy);
panel.appendChild(head);panel.appendChild(log);panel.appendChild(chipBox);panel.appendChild(form);panel.appendChild(foot);
function add(role,text){var m=el('div','ai-msg '+role);var paras=String(text).split(/\n{2,}/);paras.forEach(function(p){render(m,p);});log.appendChild(m);log.scrollTop=log.scrollHeight;return m;}
function inline(parent,t){t.split(/(\*\*[^*]+\*\*)/).forEach(function(s){if(/^\*\*[^*]+\*\*$/.test(s)){parent.appendChild(el('strong',null,s.slice(2,-2)));}else if(s){parent.appendChild(document.createTextNode(s.replace(/`/g,'')));}});}
function render(m,p){var lines=p.split('\n').filter(function(x){return x.trim();});if(!lines.length)return;
 if(lines.every(function(l){return /^\s*([-*\u2022]|\d+[.)])\s+/.test(l);})){var ul=el('ul');lines.forEach(function(l){var li=el('li');inline(li,l.replace(/^\s*([-*\u2022]|\d+[.)])\s+/,''));ul.appendChild(li);});m.appendChild(ul);return;}
 lines.forEach(function(l){var q=el('p');inline(q,l.replace(/^#+\s*/,''));m.appendChild(q);});}
function open(v){panel.hidden=!v;fab.setAttribute('aria-expanded',String(v));fab.classList.toggle('open',v);if(v){if(!log.children.length)add('bot','Hi! I can explain how the rankings work and what every factor means: pressure, uplift, intervals, sample sizes, pools and more. Pick a question or ask your own.');setTimeout(function(){input.focus();},50);}}
fab.addEventListener('click',function(){open(panel.hidden);});close.addEventListener('click',function(){open(false);fab.focus();});
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!panel.hidden)open(false);});
chips.forEach(function(c){var b=el('button','ai-chip',c);b.type='button';b.addEventListener('click',function(){ask(c);});chipBox.appendChild(b);});
form.addEventListener('submit',function(e){e.preventDefault();ask(input.value);});
input.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask(input.value);}});
function ask(q){q=String(q||'').trim();if(!q||busy)return;busy=true;send.disabled=true;chipBox.hidden=true;input.value='';add('user',q);history.push({role:'user',content:q});
 var wait=add('bot wait','Thinking\u2026');
 fetch('/api/assistant',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:history.slice(-6)})})
 .then(function(r){return r.json().catch(function(){return {};}).then(function(j){return {ok:r.ok,j:j};});})
 .then(function(x){wait.remove();if(x.ok&&x.j.answer){history.push({role:'assistant',content:x.j.answer});add('bot',x.j.answer);}else{history.pop();add('bot err',(x.j&&x.j.message)||'The assistant could not answer just now. Please try again.');}})
 .catch(function(){wait.remove();history.pop();add('bot err','The assistant could not connect. Please check your connection and try again.');})
 .then(function(){busy=false;send.disabled=false;input.focus();});}
function mount(){document.body.appendChild(panel);document.body.appendChild(fab);}
if(document.body)mount();else document.addEventListener('DOMContentLoaded',mount);
})();
