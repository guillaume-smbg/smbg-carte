-- Schéma Supabase de base pour SMBG Carte

create table if not exists contacts (
  id uuid primary key default gen_random_uuid(),
  type_profile text check (type_profile in ('enseigne','agent','autre')),
  first_name text not null,
  last_name text not null,
  email text not null,
  phone_e164 text not null,
  agency_name text,
  company text,
  company_activity text,
  role text,
  is_national boolean,
  region_zone text,
  countries text[] default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create unique index if not exists contacts_unique_person
on contacts (lower(first_name), lower(last_name), phone_e164);

create table if not exists form_submissions (
  id uuid primary key default gen_random_uuid(),
  contact_id uuid references contacts(id) on delete cascade,
  payload jsonb,
  created_at timestamptz default now()
);

create table if not exists favorites (
  id uuid primary key default gen_random_uuid(),
  contact_id uuid references contacts(id) on delete cascade,
  listing_id text not null,
  created_at timestamptz default now()
);

create table if not exists events (
  id uuid primary key default gen_random_uuid(),
  session_id text,
  contact_id uuid references contacts(id) on delete set null,
  event_type text,
  listing_id text,
  payload jsonb,
  created_at timestamptz default now()
);

create table if not exists approvals (
  id uuid primary key default gen_random_uuid(),
  contact_id uuid references contacts(id) on delete cascade,
  listing_id text not null,
  allow_rent boolean default false,
  approved_at timestamptz
);

create table if not exists versions (
  id uuid primary key default gen_random_uuid(),
  label text,
  nb_active int,
  published_at timestamptz default now()
);

create table if not exists attachments (
  id uuid primary key default gen_random_uuid(),
  contact_id uuid references contacts(id) on delete cascade,
  file_url text,
  file_name text,
  created_at timestamptz default now()
);
