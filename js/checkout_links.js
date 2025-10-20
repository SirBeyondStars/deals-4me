// Replace these with your real Stripe checkout links
const links = {
  supporter: "https://buy.stripe.com/test_supporter",
  gold: "https://buy.stripe.com/test_gold",
  pro: "https://buy.stripe.com/test_pro",
  founding: "https://buy.stripe.com/test_founding",
  donate: "https://buy.stripe.com/test_donate"
};
function wireButtons(){
  const map = [
    ["btnSupporter", links.supporter],
    ["btnGold", links.gold],
    ["btnPro", links.pro],
    ["btnFounding", links.founding],
    ["btnDonate", links.donate]
  ];
  map.forEach(([id, url])=>{
    const el = document.getElementById(id);
    if(el && url) el.href = url;
  });
}
document.addEventListener("DOMContentLoaded", wireButtons);
