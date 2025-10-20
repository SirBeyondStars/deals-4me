// Deals‑4Me Sponsor Slot (multi‑mode)
(function(){
  // ===== SETTINGS =====
  // Modes: "slideshow" (default) or "single"
  var mode = "slideshow";

  // Slideshow images (swap with real brand assets/links)
  var sponsorImages = [
    { src: "images/placeholder1.jpg", link: "#" },
    { src: "images/placeholder2.jpg", link: "#" },
    { src: "images/placeholder3.jpg", link: "#" }
  ];

  // Single sponsor
  var singleSponsor = { src: "images/walmart.jpg", link: "https://www.walmart.com" };

  // Timing (ms)
  var slideDelay = 5000;

  // ===== RUNTIME =====
  var idx = 0;
  var img = document.getElementById("sponsor-image");
  var a   = document.getElementById("sponsor-link");
  var timer;

  function renderSlide(){
    img.src = sponsorImages[idx].src;
    a.href  = sponsorImages[idx].link || "#";
    idx = (idx + 1) % sponsorImages.length;
  }

  function start(){
    // Ensure first frame renders immediately
    if(mode === "slideshow"){
      renderSlide();
      timer = setInterval(renderSlide, slideDelay);
      bindHoverPause();
    }else if(mode === "single"){
      img.src = singleSponsor.src;
      a.href  = singleSponsor.link || "#";
    }
  }

  function bindHoverPause(){
    var box = document.getElementById("sponsor-container");
    if(!box) return;
    box.addEventListener("mouseenter", function(){ if(timer) clearInterval(timer); });
    box.addEventListener("mouseleave", function(){ if(mode === "slideshow") timer = setInterval(renderSlide, slideDelay); });
  }

  // Expose a quick API on window for future admin toggles
  window.Deals4MeSponsor = {
    setMode: function(m){
      mode = m === "single" ? "single" : "slideshow";
      if(timer) clearInterval(timer);
      start();
    },
    setSingle: function(obj){
      singleSponsor = obj || singleSponsor;
      if(mode === "single"){ img.src = singleSponsor.src; a.href = singleSponsor.link || "#"; }
    },
    setSlides: function(arr){
      sponsorImages = Array.isArray(arr) && arr.length ? arr : sponsorImages;
      idx = 0;
      if(mode === "slideshow"){ renderSlide(); }
    }
  };

  // Kick off
  document.readyState === "loading" ?
    document.addEventListener("DOMContentLoaded", start) :
    start();
})();
