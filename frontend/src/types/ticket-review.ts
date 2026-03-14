export type ReviewStatus =
  | 'confirmed'
  | 'very_likely'
  | 'possible'
  | 'not_100_percent_sure'
  | 'rejected';

export interface ScreenshotItem {
  id: string;
  imageUrl: string;
  frameTimestampMs: number;
  videoTimestampLabel: string;
  capturedAt: string;
  capturedBy?: string;
  note?: string;
}

export interface RegistryMatch {
  found: boolean;
  make?: string;
  model?: string;
  color?: string;
  year?: string | number;
}

export interface VehicleGuess {
  make?: string;
  model?: string;
  color?: string;
}

export interface ParkingContext {
  nearRedWhiteCurb?: boolean;
  onSidewalk?: boolean;
  stationaryDurationSeconds?: number;
  trafficFlowState?: 'flowing' | 'congested' | 'unknown';
}

export interface TicketReviewData {
  id: string | number;
  status: ReviewStatus;
  confidenceLabel?: string;
  reason?: string;
  plateText?: string;
  plateCandidates?: string[];
  videoUrl: string;
  videoStartedAt?: string;
  durationSeconds?: number;
  sourceVideoHash?: string;
  registry?: RegistryMatch;
  vehicle?: VehicleGuess;
  parkingContext?: ParkingContext;
  screenshots?: ScreenshotItem[];
}
