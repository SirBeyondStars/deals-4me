// Flyer-only sale data (safe to display with attribution)
// Replace/append with your parsed weekly ads.
window.SALES_FEED = [
  { id:"tomato-sauce-24oz", name:"Tomato Sauce, 24oz", store:"Market Basket", salePrice:1.79, validThrough:"2025-08-16" },
  { id:"ground-beef-80-20-1lb", name:"Ground Beef 80/20, 1 lb", store:"Stop & Shop", salePrice:3.99, validThrough:"2025-08-15" },
  { id:"garlic-head", name:"Garlic, 1 head", store:"Shaw's", salePrice:0.59, validThrough:"2025-08-18" },
  { id:"spaghetti-1lb", name:"Spaghetti, 1 lb", store:"Hannaford", salePrice:1.19, validThrough:"2025-08-14" }
];

// Simple keyword index (case-insensitive contains)
window.buildSalesIndex = function(){
  const idx = new Map();
  for(const item of window.SALES_FEED){
    const keys = [
      item.name.toLowerCase(),
      ...item.name.toLowerCase().split(/[\s,/-]+/).filter(Boolean)
    ];
    keys.forEach(k=>{
      if(!idx.has(k)) idx.set(k, []);
      idx.get(k).push(item);
    });
  }
  return idx;
};
