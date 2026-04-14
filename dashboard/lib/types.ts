export type UserRole = "operator" | "owner";
export type BookingStatus =
  | "confirmed"
  | "modified"
  | "cancelled"
  | "no_show"
  | "completed";
export type BookingSource = "ai_phone" | "dashboard" | "walk_in";
export type CallOutcome =
  | "booking_created"
  | "booking_modified"
  | "booking_cancelled"
  | "info_provided"
  | "escalated"
  | "abandoned"
  | "tool_error";
export type CallStatus = "successful" | "failed" | "unknown";
export type VoiceProvider = "openai_realtime" | "elevenlabs";

export interface SessionUser {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  restaurant_id: string | null;
  restaurant_ids: string[];
}

export interface SessionResponse {
  user: SessionUser;
}

export interface RestaurantSummary {
  id: string;
  slug: string;
  name: string;
  twilio_phone: string | null;
  is_active: boolean;
  calls_today: number;
  bookings_today: number;
  booking_rate: number;
}

export interface RestaurantSyncStatus {
  synced: boolean;
  message: string;
}

export interface Restaurant {
  id: string;
  slug: string;
  name: string;
  twilio_phone: string | null;
  voice_provider: VoiceProvider;
  timezone: string;
  address: string;
  opening_hours: Record<string, string>;
  weekly_closures: string[];
  closure_dates: string[];
  turni: Array<{ name: string; start: string; end: string; max_covers: number }>;
  booking_rules: Record<string, number>;
  custom_greeting: string | null;
  agent_style_notes: string | null;
  escalation_phone: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  sync_status?: RestaurantSyncStatus | null;
}

export interface Booking {
  id: string;
  restaurant_id: string;
  confirmation_code: string;
  date: string;
  time: string;
  turno: string;
  party_size: number;
  customer_name: string;
  customer_phone: string;
  special_requests: string | null;
  status: BookingStatus;
  source: BookingSource;
  customer_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface BookingEvent {
  id: string;
  booking_id: string;
  event_type: string;
  changed_by: string | null;
  changes: Record<string, unknown>;
  created_at: string;
}

export interface CallLog {
  id: string;
  restaurant_id: string;
  voice_provider: VoiceProvider;
  provider_call_id: string | null;
  twilio_call_sid: string | null;
  started_at: string;
  duration_seconds: number;
  outcome: CallOutcome;
  call_status: CallStatus;
  booking_id: string | null;
  summary: string;
  transcript_preview: string | null;
  caller_phone: string | null;
  customer_name: string | null;
  party_size: number | null;
  requested_date: string | null;
  requested_time: string | null;
}

export interface TranscriptResponse {
  call_id: string;
  source: string;
  summary: string;
  transcript: string | null;
  metadata: Record<string, unknown>;
}

export interface MetricStat {
  value: number;
  delta_vs_yesterday: number;
  delta_vs_7d_avg: number;
  status: string;
}

export interface ActivityItem {
  id: string;
  kind: string;
  title: string;
  detail: string;
  created_at: string;
  tone: string;
}

export interface DemandGap {
  label: string;
  total_requests: number;
}

export interface AnalyticsOverview {
  calls_today: MetricStat;
  bookings_today: MetricStat;
  booking_rate_today: MetricStat;
  recent_activity: ActivityItem[];
  demand_gaps: DemandGap[];
}

export interface TrendPoint {
  date: string;
  calls: number;
  bookings: number;
  booking_rate: number;
}

export interface HeatmapCell {
  weekday: number;
  hour: number;
  calls: number;
}

export interface EscalationBreakdown {
  outcome: string;
  total: number;
}

export interface TrendBundle {
  points: TrendPoint[];
  heatmap: HeatmapCell[];
  escalations: EscalationBreakdown[];
}

export interface CapacitySlot {
  turno: string;
  start: string;
  end: string;
  booked_covers: number;
  max_covers: number;
  remaining_covers: number;
  occupancy_ratio: number;
}

export interface CapacitySnapshot {
  restaurant_id: string;
  date: string;
  slots: CapacitySlot[];
}

export interface OwnerAgendaSummary {
  today_booked_covers: number;
  today_calls: number;
  today_unresolved_calls: number;
}

export interface OwnerAgendaTurno {
  turno: string;
  start: string;
  end: string;
  booked_covers: number;
  booking_count: number;
  max_covers: number;
  remaining_covers: number;
  occupancy_ratio: number;
  fullness: "low" | "healthy" | "full" | "overbooked-risk";
}

export interface OwnerAgendaDay {
  date: string;
  weekday_label: string;
  is_today: boolean;
  is_closed: boolean;
  closure_label: string | null;
  total_booked_covers: number;
  total_booking_count: number;
  total_remaining_covers: number;
  turni: OwnerAgendaTurno[];
}

export interface OwnerAgendaResponse {
  restaurant_id: string;
  timezone: string;
  days: OwnerAgendaDay[];
  summary: OwnerAgendaSummary;
}

export interface StudioChecklistItem {
  label: string;
  status: string;
  detail: string;
}

export interface StudioPreset {
  id: string;
  label: string;
  description: string;
  session_overrides: StudioSessionOverrides;
}

export interface StudioScenario {
  id: string;
  label: string;
  message: string;
  goal: string;
}

export interface StudioConfigDiffItem {
  field: string;
  label: string;
  baseline: string;
  effective: string;
  source: string;
}

export interface StudioAgentPreview {
  prompt: string;
  session_update: Record<string, unknown>;
  tools: Array<Record<string, unknown>>;
  checklist: StudioChecklistItem[];
  readiness: StudioChecklistItem[];
  prompt_diagnostics: StudioChecklistItem[];
  recommendations: StudioChecklistItem[];
  config_diff: StudioConfigDiffItem[];
  presets: StudioPreset[];
  scenarios: StudioScenario[];
  saved_prompt_override?: string | null;
  saved_session_overrides?: StudioSessionOverrides;
  default_session_overrides?: StudioSessionOverrides;
  effective_session_overrides?: StudioSessionOverrides;
}

export interface StudioSessionOverrides {
  model?: string | null;
  voice?: string | null;
  tool_choice?: "auto" | "none" | "required" | null;
  temperature?: number | null;
  speed?: number | null;
  max_response_output_tokens?: number | null;
  turn_detection_type?: "server_vad" | "semantic_vad" | null;
  vad_threshold?: number | null;
  vad_prefix_padding_ms?: number | null;
  vad_silence_duration_ms?: number | null;
  vad_idle_timeout_ms?: number | null;
  semantic_vad_eagerness?: "low" | "medium" | "high" | "auto" | null;
  interrupt_response?: boolean | null;
  create_response?: boolean | null;
  noise_reduction_type?: "near_field" | "far_field" | "off" | null;
  transcription_model?: string | null;
  input_language?: string | null;
  tracing_enabled?: boolean | null;
  truncation_mode?: "retention_ratio" | "disabled" | null;
  truncation_retention_ratio?: number | null;
  truncation_post_instructions_tokens?: number | null;
}

export interface StudioToolTestResponse {
  result: Record<string, unknown>;
}

export interface StudioTranscriptTurn {
  role: string;
  content: string;
}

export interface StudioSimulationResponse {
  assistant_message: string;
  transcript: StudioTranscriptTurn[];
  tool_events: Array<Record<string, unknown>>;
  usage: Record<string, unknown> | null;
}

export interface StudioConfigUpdateResponse {
  ok: boolean;
  saved_prompt_override?: string | null;
  saved_session_overrides?: StudioSessionOverrides;
  deployed: boolean;
  deployment_status: "live" | "warning";
  deployment_message: string;
  effective_prompt: string;
  effective_prompt_hash: string;
  effective_session_overrides: StudioSessionOverrides;
  prompt_diagnostics: StudioChecklistItem[];
  published_at?: string | null;
}
