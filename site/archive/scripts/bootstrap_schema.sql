create table if not exists public.flyer_weeks (
  id uuid primary key default gen_random_uuid(),
  store_slug text not null,
  week_code text not null,
  start_date date,
  end_date date,
  region text,
  created_at timestamptz default now()
);
create unique index if not exists flyer_weeks_unique
  on public.flyer_weeks (store_slug, week_code);

create table if not exists public.flyer_items (
  id uuid primary key default gen_random_uuid(),
  store_slug text not null,
  week_code text not null,
  region text,
  item_name text not null,
  price_cents integer not null,
  created_at timestamptz default now()
);
create table if not exists public.flyer_raw_lines (
  id bigserial primary key,
  store_slug text not null,
  week_code text not null,
  region text,
  source_file text,
  line_no integer,
  content text,
  created_at timestamptz default now()
);
