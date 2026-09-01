import type { Metadata } from "next";
import ProductHome from "@/components/home/ProductHome";

export const metadata: Metadata = {
  title: "Outreach — Personal emails, from one simple workspace",
  description: "Import contacts from CSV, pasted rows, or Google Sheets. Write personal emails, choose your senders and schedule, and review before sending with Outreach.",
};

export default function Home() {
  return <ProductHome />;
}
