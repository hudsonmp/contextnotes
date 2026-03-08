-- ContextNotes: Initial Supabase Schema
-- Three-layer learning trace architecture
-- Layer 1: Behavioral Events (sessions, events)
-- Layer 2: Sensor Streams (gaze_stream, screen_captures)
-- Layer 3: Derived Analytics (session_analytics)

-- Sessions: a reading + note-taking session
create table sessions (
  id uuid primary key default gen_random_uuid(),
  started_at timestamptz not null,
  ended_at timestamptz,
  article_url text not null,
  article_title text,
  notebook_name text,
  status text not null default 'active'
    check (status in ('active', 'paused', 'completed')),
  created_at timestamptz not null default now()
);

create index idx_sessions_status on sessions(status);
create index idx_sessions_started_at on sessions(started_at);

-- Layer 1: Behavioral events
-- Reading scrolls, paragraph focus, annotation creation, etc.
-- source_data and annotation_data are JSONB for flexibility (W3C WADM selectors, viewport state)
create table events (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references sessions(id) on delete cascade,
  timestamp timestamptz not null,
  event_type text not null
    check (event_type in (
      'reading.scroll',
      'reading.focus_paragraph',
      'reading.selection',
      'reading.navigate',
      'annotation.create',
      'annotation.update',
      'gaze.fixation',
      'session.start',
      'session.pause',
      'session.resume',
      'session.end'
    )),
  source_data jsonb,
  annotation_data jsonb,
  created_at timestamptz not null default now()
);

create index idx_events_session on events(session_id);
create index idx_events_timestamp on events(timestamp);
create index idx_events_type on events(event_type);
create index idx_events_session_timestamp on events(session_id, timestamp);

-- Layer 2: Gaze + scroll stream
-- High-frequency time-series from WebGazer.js and Chrome scroll position
-- gaze_x/y may be null when only scroll proxy is available
create table gaze_stream (
  id bigint generated always as identity primary key,
  session_id uuid not null references sessions(id) on delete cascade,
  timestamp timestamptz not null,
  gaze_x real,
  gaze_y real,
  gaze_confidence real,
  scroll_y real,
  scroll_progress real
);

create index idx_gaze_session_timestamp on gaze_stream(session_id, timestamp);

-- Layer 2: Screen captures from GoodNotes window
-- Each frame is a screenshot; diff_detected indicates new ink
create table screen_captures (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references sessions(id) on delete cascade,
  timestamp timestamptz not null,
  frame_number integer not null,
  screenshot_url text,
  diff_detected boolean not null default false,
  new_ink_region jsonb,
  created_at timestamptz not null default now()
);

create index idx_captures_session_timestamp on screen_captures(session_id, timestamp);
create index idx_captures_diff on screen_captures(session_id) where diff_detected = true;

-- Layer 3: Derived session analytics
-- Computed post-session by Claude API analysis
create table session_analytics (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references sessions(id) on delete cascade,
  reading_path jsonb,
  annotation_timeline jsonb,
  thought_progression text,
  concept_map jsonb,
  learning_indicators jsonb,
  computed_at timestamptz not null default now()
);

create index idx_analytics_session on session_analytics(session_id);

-- Storage bucket for screenshots
-- Run via Supabase dashboard or API: create bucket 'screenshots' (public: false)

-- Row-level security (optional, for multi-user)
-- For single-user prototype, RLS can be disabled
