const list=document.getElementById('newsList');
const stamp=document.getElementById('newsStamp');
const fmt=d=>new Date(d+'T00:00:00Z').toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'});
function node(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e;}
try{
 const res=await fetch('./news.json');if(!res.ok)throw new Error('news unavailable');
 const news=await res.json();
 stamp.textContent='Reports checked '+fmt(news.checked);
 const items=[...news.items].sort((a,b)=>b.date.localeCompare(a.date));
 for(const n of items){
  const card=node('article','news-card '+n.status);
  const top=node('div','news-top');
  top.append(node('span','news-badge',n.status==='confirmed'?'Confirmed':'Reported'),node('time','news-date',fmt(n.date)));
  const link=node('a','news-link',n.source+' \u2197');link.href=n.url;link.target='_blank';link.rel='noopener noreferrer';
  card.append(top,node('h3',null,n.title),node('p',null,n.summary),link);
  list.append(card);
 }
}catch(e){list.append(node('p','news-empty','Auction news is not available right now.'));}
