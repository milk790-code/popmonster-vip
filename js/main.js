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

// === Category Filter + Search (index only) ===
(function(){
  var btns=document.querySelectorAll('.filter-btn');
  var cards=document.querySelectorAll('.card[data-cat]');
  var searchInput=document.getElementById('product-search');
  var emptyMsg=document.getElementById('search-empty');
  if(!cards.length)return;

  var state={cat:'all',q:''};

  function norm(s){return (s||'').toLowerCase().trim()}

  function apply(){
    var q=state.q,cat=state.cat,visible=0;
    cards.forEach(function(c){
      var matchCat=(cat==='all'||c.dataset.cat===cat);
      var matchQ=true;
      if(q){
        var txt=norm(c.textContent);
        matchQ=txt.indexOf(q)>-1;
      }
      var show=matchCat&&matchQ;
      c.style.display=show?'':'none';
      if(show)visible++;
    });
    if(emptyMsg){emptyMsg.classList.toggle('show',visible===0)}
  }

  btns.forEach(function(b){
    b.addEventListener('click',function(){
      btns.forEach(function(x){x.classList.remove('active')});
      b.classList.add('active');
      state.cat=b.dataset.cat;
      apply();
    });
  });

  if(searchInput){
    var t;
    searchInput.addEventListener('input',function(){
      clearTimeout(t);
      t=setTimeout(function(){state.q=norm(searchInput.value);apply()},120);
    });
  }
})();
