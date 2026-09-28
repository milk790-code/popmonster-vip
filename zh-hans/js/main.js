// === Carousel 主打商品轮播 ===
(function(){
  var track = document.querySelector('.carousel-track');
  if(!track) return;
  var slides = track.querySelectorAll('.carousel-slide');
  var dots = document.querySelectorAll('.carousel-dot');
  var prev = document.querySelector('.carousel-btn.prev');
  var next = document.querySelector('.carousel-btn.next');
  var current = 0;
  var total = slides.length;
  var timer;
  
  function go(idx){
    current = (idx + total) % total;
    track.style.transform = 'translateX(-' + (current * 100) + '%)';
    dots.forEach(function(d,i){d.classList.toggle('active', i === current)});
  }
  
  function start(){ timer = setInterval(function(){ go(current + 1) }, 5000); }
  function stop(){ clearInterval(timer); }
  
  prev && prev.addEventListener('click', function(){ go(current - 1); stop(); start(); });
  next && next.addEventListener('click', function(){ go(current + 1); stop(); start(); });
  dots.forEach(function(d,i){ d.addEventListener('click', function(){ go(i); stop(); start(); })});
  
  // hover 暂停
  var carousel = document.querySelector('.carousel');
  if(carousel){
    carousel.addEventListener('mouseenter', stop);
    carousel.addEventListener('mouseleave', start);
  }
  
  // 触摸滑动
  var startX = 0;
  track.addEventListener('touchstart', function(e){ startX = e.touches[0].clientX; stop(); }, {passive:true});
  track.addEventListener('touchend', function(e){
    var dx = e.changedTouches[0].clientX - startX;
    if(dx > 50) go(current - 1);
    else if(dx < -50) go(current + 1);
    start();
  });
  
  start();
})();

// === Cookie Consent + GA4 Consent Mode v2 ===
(function(){
  var bar=document.querySelector('.cookie-bar');
  if(!bar)return;
  
  // 检查既有同意状态
  var existing = localStorage.getItem('ck_consent');
  if(existing === 'granted' && typeof gtag === 'function'){
    // 用户之前已同意，立刻升级
    gtag('consent','update',{
      'ad_storage':'granted',
      'ad_user_data':'granted',
      'ad_personalization':'granted',
      'analytics_storage':'granted'
    });
    if(typeof window.loadAnalytics === 'function') window.loadAnalytics();
    return;
  }
  if(existing === 'denied') return;
  
  // 没有同意纪录，显示 Cookie Bar
  setTimeout(function(){bar.classList.add('show')},800);
  
  document.getElementById('ck-accept')&&document.getElementById('ck-accept').addEventListener('click',function(){
    if(typeof gtag === 'function'){
      gtag('consent','update',{
        'ad_storage':'granted',
        'ad_user_data':'granted',
        'ad_personalization':'granted',
        'analytics_storage':'granted'
      });
    }
    if(typeof window.loadAnalytics === 'function') window.loadAnalytics();
    localStorage.setItem('ck_consent','granted');
    bar.classList.remove('show');
  });
  
  document.getElementById('ck-decline')&&document.getElementById('ck-decline').addEventListener('click',function(){
    localStorage.setItem('ck_consent','denied');
    bar.classList.remove('show');
  });
})();

// === Scroll Progress Bar 页面进度条 ===
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

// === Back to Top 回顶部 ===
(function(){
  var btn=document.createElement('button');
  btn.className='back-top';
  btn.innerHTML='↑';
  btn.setAttribute('aria-label','回到顶部');
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
