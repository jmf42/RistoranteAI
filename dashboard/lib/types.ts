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
  elevenlabs_agent_id: string | null;
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
  elevenlabs_conversation_id: string | null;
  started_at: string;
  duration_seconds: number;
  outcome: CallOutcome;
  call_status: CallStatus;
  booking_id: string | null;
  summary: string;
  transcript_preview: string | null;
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
