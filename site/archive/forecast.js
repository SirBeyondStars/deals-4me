// /site/js/forecast.js
import { supabase } from './auth.js'; // use your existing client

async function loadUserForecasts() {
  const { data: { user }, error: userError } = await supabase.auth.getUser();
  if (userError || !user) {
    document.getElementById('forecastGrid').innerHTML =
      '<p class="text-red-600">Please log in to view forecasts.</p>';
    return;
  }

  const { data: forecasts, error } = await supabase.rpc('forecasts_for_user_limited', {
    p_user: user.id,
    p_banner: null
  });

  if (error) {
    document.getElementById('forecastGrid').innerHTML =
      `<p class="text-red-600">Error loading forecasts: ${error.message}</p>`;
    return;
  }

  const grid = document.getElementById('forecastGrid');
  grid.innerHTML = '';

  forecasts.forEach(row => {
    const isLikely = row.forecast_label === 'likely';
    const dotClass = isLikely ? 'bg-green-500' : 'bg-gray-400';
    grid.insertAdjacentHTML('beforeend', `
      <div class="border rounded-2xl shadow p-4 bg-white hover:shadow-lg transition">
        <div class="flex justify-between items-center mb-2">
          <h2 class="font-semibold text-lg">${row.item_name_norm}</h2>
          <span class="inline-block w-3 h-3 rounded-full ${dotClass}"></span>
        </div>
        <p class="text-sm text-gray-600">${row.banner || 'Unknown store'}</p>
        <p class="text-sm mt-2"><strong>Sale probability:</strong> ${Math.round(row.p_sale_next_week * 100)}%</p>
        <p class="text-sm"><strong>Days since last sale:</strong> ${row.days_since_last_sale}</p>
      </div>
    `);
  });
}

loadUserForecasts();
