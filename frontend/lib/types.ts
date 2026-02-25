export type GenerationStatus = "pending" | "generating" | "done" | "error";

export type AnalysisStatus = "pending" | "running" | "done" | "failed";

export type JewelryCategory = "ring" | "necklace" | "bracelet" | "earrings";

export type FeedbackAction = "like" | "dislike" | "save";

export type ScreenPhase = "upload" | "review" | "finalization";

export type DynamicChip = {
  id: string;
  label: string;
  dimensions: string[];
};

export type ImageAnalysisData = {
  like_chips: DynamicChip[];
  dislike_chips: DynamicChip[];
  chip_dimension_map: Record<string, string[]>;
};

export type Candidate = {
  candidate_id: string;
  generation_status: GenerationStatus;
  image_url: string | null;
  error: string | null;
  analysis_status: AnalysisStatus;
  image_analysis: ImageAnalysisData | null;
};

export type SessionState = {
  session_id: string;
  user_id: string;
  round_number: number;
  candidates: Candidate[];
};

export type FinalizeResult = {
  session_id: string;
  hero_image_url: string;
  export_variants: {
    feed_1x1: string;
    story_9x16: string;
  };
};

export type ActionFeedback = {
  submitted: boolean;
  chips: string[];
  chipDimMap: Record<string, string[]>;
  note?: string;
};

export type CandidateLocalFeedback = {
  like: ActionFeedback;
  dislike: ActionFeedback;
  save: boolean;
};

// Chip definitions (must match backend DISLIKE_CHIPS / LIKE_CHIPS)
export type ChipTag = {
  id: string;
  label: string;
};

export const LIKE_CHIPS: ChipTag[] = [
  { id: "love_lighting", label: "Love lighting" },
  { id: "great_composition", label: "Great composition" },
  { id: "model_works", label: "Model works" },
  { id: "premium_feel", label: "Premium feel" },
  { id: "product_pops", label: "Product pops" },
];

export const DISLIKE_CHIPS: ChipTag[] = [
  { id: "too_dark", label: "Too dark" },
  { id: "too_busy", label: "Too busy" },
  { id: "model_distracts", label: "Model distracts" },
  { id: "not_realistic", label: "Not realistic" },
  { id: "product_unclear", label: "Product unclear" },
  { id: "wrong_vibe", label: "Wrong vibe" },
];
