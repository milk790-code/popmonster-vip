// === Cookie Consent ===
(function(){
  var bar=document.querySelector('.cookie-bar');
  if(!bar)return;
  if(localStorage.getItem('ck_consent'))return;
  setTimeout(function(){bar.classList.add('show')},1500);
  document.getElementById('ck-accept')&&document.getElementById('ck-accept').addEventListener('click',function(){
    localStorage.setItem('ck_consent','granted');bar.classList.remove('show');
  });
  document.getElementById('ck-decline')&&document.getElementById('ck-decline').addEventListener('click',function(){
    localStorage.setItem('ck_consent','denied');bar.classList.remove('show');
  });
})();

// === Scroll Progress Bar 頁面進度條 ===
(function(){
  var bar=document.createElement('div');
  bar.className='progress-bar';
  document.body.prepend(bar);
  window.addEventListener('scroll',function(){
    var h=document.documentElement;
    var pct=(h.scrollTop/(h.scrollHeight-h.clientHeight))*100;
    bar.style.width=Math.min(pct,100)+'%';
  },{passive:true});
})();

// === Back to Top 回頂部 ===
(function(){
  var btn=document.createElement('button');
  btn.className='back-top';
  btn.innerHTML='↑';
  btn.setAttribute('aria-label','回到頂部');
  document.body.appendChild(btn);
  window.addEventListener('scroll',function(){
    btn.classList.toggle('show',window.scrollY>400);
  },{passive:true});
  btn.addEventListener('click',function(){
    window.scrollTo({top:0,behavior:'smooth'});
  });
})();

// === NAV Scroll Effect ===
(function(){
  var nav=document.querySelector('.nav');
  if(!nav)return;
  window.addEventListener('scroll',function(){
    nav.classList.toggle('scrolled',window.scrollY>20);
  },{passive:true});
})();

// === Scroll Fade In ===
(function(){
  var els=document.querySelectorAll('.fade-up');
  if(!els.length)return;
  var io=new IntersectionObserver(function(entries){
    entries.forEach(function(e){if(e.isIntersecting){e.target.classList.add('visible');io.unobserve(e.target)}});
  },{threshold:0.1});
  els.forEach(function(el){io.observe(el)});
})();

// === FAQ Toggle ===
document.querySelectorAll('.faq-q').forEach(function(q){
  q.addEventListener('click',function(){this.parentElement.classList.toggle('open')});
});

// === Category Filter ===
(function(){
  var btns=document.querySelectorAll('.filter-btn');
  var cards=document.querySelectorAll('.card[data-cat]');
  if(!btns.length||!cards.length)return;
  btns.forEach(function(b){
    b.addEventListener('click',function(){
      btns.forEach(function(x){x.classList.remove('active')});
      b.classList.add('active');
      var cat=b.dataset.cat;
      cards.forEach(function(c){c.style.display=(cat==='all'||c.dataset.cat===cat)?'':'none'});
    });
  });
})();
