// Deli (variable weight)
{
  id: "deli-boarshead-turkey",
  storeId: "sns-002",
  title: "Boar's Head Oven Gold Turkey",
  cat: "Deli",
  pricing_type: "per_weight",
  unit: "lb",
  price_per_unit: 12.99,
  min_increment: 0.25, // 1/4 lb steps
  options: { thickness: ["Shaved","Thin","Medium","Thick"] }
}

// Produce by count
{
  id: "produce-avocado",
  storeId: "sns-002",
  title: "Avocados",
  cat: "Produce",
  pricing_type: "per_unit",
  unit_label: "each",
  price_each: 1.29
}

// Meat — ribeye (per lb)
{
  id: "meat-ribeye",
  storeId: "shaw-001",
  title: "Ribeye Steak",
  cat: "Meat",
  pricing_type: "per_weight",
  unit: "lb",
  price_per_unit: 9.99
}
// variable weight
{
  id: "deli-boarshead-turkey@0.75lb",
  title: "Boar's Head Oven Gold Turkey",
  store: "Stop & Shop",
  pricing_type: "per_weight",
  qty: 0.75,
  unit: "lb",
  price_per_unit: 12.99,
  est_total: 9.74,
  notes: { thickness: "Thin", instructions: "shaved if possible" }
}

// by count
{
  id: "produce-avocado@3",
  title: "Avocados",
  store: "Stop & Shop",
  pricing_type: "per_unit",
  qty: 3,
  unit_label: "each",
  price_each: 1.29,
  est_total: 3.87
}
