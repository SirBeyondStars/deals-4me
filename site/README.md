# Deals‑4Me Sponsor Slot (No Images)

This is a reusable component you can drop into any page. It supports:
- **Slideshow mode** (default) — rotate through multiple sponsor images
- **Single mode** — show one static sponsor banner

## Files
- `sponsor-slot.html` — demo page
- `sponsor-slot.css` — fixed sizing so layout never jumps
- `sponsor-slot.js` — logic for slideshow/single + pause on hover

## How to use
1) Copy `sponsor-slot.css` and `sponsor-slot.js` into your project.
2) Add this markup where you want the slot to appear:

<link rel="stylesheet" href="sponsor-slot.css">
<div id="sponsor-container">
  <a id="sponsor-link" href="#" target="_blank" rel="noopener">
    <img id="sponsor-image" src="images/placeholder1.jpg" alt="Sponsor">
  </a>
</div>
<script src="sponsor-slot.js"></script>

3) Put your images under `images/` and edit `sponsor-slot.js`:
   - For slideshow: update `sponsorImages = [{src, link}, ...]`
   - For single banner: set `mode = "single"` and set `singleSponsor = {src, link}`

## Optional Console Controls
Deals4MeSponsor.setMode("single"); // or "slideshow")
Deals4MeSponsor.setSingle({ src:"images/target.jpg", link:"https://target.com" });
Deals4MeSponsor.setSlides([{src:"images/campbells.jpg", link:"#"}, {src:"images/lays.jpg", link:"#"}]);
