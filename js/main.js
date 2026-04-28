// === Cookie Consent ===
(function(){
  var bar=document.querySelector('.cookie-bar');
  if(!bar)return;
  if(localStorage.getItem('ck_consent'))return;
  setTimeout(function(){bar.classList.add('show')},1500);
  document.getElementById('ck-accept')&&document.getElementById('ck-accept').addEventListener('click',function(){
    if(typeof gtag==='function'){gtag('consent','update',{'ad_storage':'granted','ad_user_data':'granted','ad_personalization':'granted','analytics_storage':'granted'})}
    localStorage.setItem('ck_consent','granted');bar.classList.remove('show');
  });
  document.getElementById('ck-decline')&&document.getElementById('ck-decline').addEventListener('click',function(){
    localStorage.setItem('ck_consent','denied');bar.classList.remove('show');
  });
})();

// === Scroll Fade In ===
(function(){
  var els=document.querySelectorAll('.fade-up');
  if(!els.length)return;
  var io=new IntersectionObserver(function(entries){
    entries.forEach(function(e){if(e.isIntersecting){e.target.classList.add('visible');io.unobserve(e.target)}});
  },{threshold:0.15});
  els.forEach(function(el){io.observe(el)});
})();

// === FAQ Toggle ===
document.querySelectorAll('.faq-q').forEach(function(q){
  q.addEventListener('click',function(){this.parentElement.classList.toggle('open')});
});

// === Category Filter (index only) ===
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
