// 在已登录的 book.douban.com 页面里运行（Claude in Chrome javascript_tool）。
// 逐页抓取「读过」列表，结果存到 window.__db.items；完成后 window.__db.done=true。
// 字段：id=豆瓣 subject id, t=书名, sub=副标题, pub=作者/出版信息, r=星级(1-5), d=读完日期, tags=标签, c=短评
// 用法：把 USER 换成豆瓣用户 ID；增量同步时把 MAX_PAGES 设为 1–2。
const USER='67681196', MAX_PAGES=40;
window.__db={items:[],done:false,err:null,page:0};
const parse=(doc)=>[...doc.querySelectorAll('.subject-item')].map(li=>{const a=li.querySelector('.info h2 a');const r=li.querySelector('[class^="rating"]');return {id:(a?.getAttribute('href').match(/subject\/(\d+)/)||[])[1],t:(a?.getAttribute('title')||a?.textContent||'').trim(),sub:(li.querySelector('.info h2 span')?.textContent||'').trim().replace(/^:\s*/,''),pub:(li.querySelector('.pub')?.textContent||'').trim(),r:r?+(r.className.match(/rating(\d)/)||[])[1]:null,d:((li.querySelector('.date')?.textContent||'').match(/\d{4}-\d{2}-\d{2}/)||[''])[0],tags:(li.querySelector('.tags')?.textContent||'').replace(/^标签:\s*/,'').trim(),c:(li.querySelector('.comment')?.textContent||'').trim()}});
(async()=>{try{for(let p=0;p<MAX_PAGES;p++){const s=p*15;window.__db.page=p;const res=await fetch(`/people/${USER}/collect?start=${s}&sort=time&rating=all&filter=all&mode=grid`,{credentials:'include'});if(!res.ok){window.__db.err='HTTP '+res.status+' at '+s;break}const doc=new DOMParser().parseFromString(await res.text(),'text/html');const got=parse(doc);if(!got.length)break;window.__db.items.push(...got);await new Promise(r=>setTimeout(r,1500+Math.random()*1000));}}catch(e){window.__db.err=String(e)}window.__db.done=true})();
// 取数据：工具单次返回很短会被截断，所以把结果写进页面再用 get_page_text 读：
// window.__slim=window.__db.items.map(x=>[x.id,x.t+(x.sub?': '+x.sub:''),x.pub.split(' / ')[0],x.r,x.d,x.tags,x.c]);
// document.body.innerHTML='<pre>'+...+'</pre>'（用 textContent 写入，每行一条 JSON）
