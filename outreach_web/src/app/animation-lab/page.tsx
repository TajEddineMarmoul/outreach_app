import type { Metadata } from "next";
import LineAnimationLab from "@/components/home/LineAnimationLab";

export const metadata: Metadata = {
  title: "Line Percentage Lab — Outreach",
  description: "Test SVG line progress and percentage-based popup positions.",
};

export default function AnimationLabPage() {
  return <LineAnimationLab />;
}
