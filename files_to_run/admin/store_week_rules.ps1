# ===== store_week_rules.ps1 =====
$Global:StoreWeekday = @{
  aldi='Wednesday'; pricerite='Wednesday';
  stopandshop='Thursday'; 'stop_and_shop_ct'='Thursday'; 'stop_and_shop_mari'='Thursday';
  shaws='Sunday'; market_basket='Sunday'; hannaford='Sunday';
  price_chopper_market_32='Sunday'; wegmans='Sunday'; roche_bros='Sunday';
  big_y='Sunday'; trucchis='Sunday'; whole_foods='Sunday'
}

function Get-StartOfStoreWeek([datetime]$nowLocal, [string]$store) {
  $want = $Global:StoreWeekday[$store]; if (-not $want) { $want = 'Sunday' }
  $target = [System.DayOfWeek]::$want
  $d = $nowLocal.Date
  while ($d.DayOfWeek -ne $target) { $d = $d.AddDays(-1) }
  $d
}

function Get-MmDdYy([datetime]$startDate) { $startDate.ToString('MMddyy') }

function Get-WeekFolderName([datetime]$startDate) {
  $week = [System.Globalization.ISOWeek]::GetWeekOfYear($startDate)
  ('Week{0:00}' -f $week)
}
# ===== end =====
