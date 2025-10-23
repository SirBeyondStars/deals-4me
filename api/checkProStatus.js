const { data: { user } } = await supabase.auth.getUser();
if (user) {
  const { data: profile } = await supabase
    .from("profiles")
    .select("is_active, plan, current_period_end")
    .eq("id", user.id)
    .single();

  if (profile?.is_active) {
    // show Pro stuff
  } else {
    // show “Upgrade” button
  }
}
