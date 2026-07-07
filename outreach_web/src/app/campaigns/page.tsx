"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR, { mutate } from "swr";
import { Plus, Mail, ArrowRight, Loader2 } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const fetcher = (url: string) => fetch(url).then((r) => {
  if (!r.ok) throw new Error("API call failed");
  return r.json();
});

export default function CampaignsPage() {
  const { data: campaigns, error, isLoading } = useSWR(`${API_URL}/api/campaigns`, fetcher);
  const [isOpen, setIsOpen] = useState(false);
  const [campaignName, setCampaignName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [subError, setSubError] = useState("");

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!campaignName.trim()) return;
    setIsSubmitting(true);
    setSubError("");
    try {
      const res = await fetch(`${API_URL}/api/campaigns`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: campaignName.trim() }),
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to create campaign");
      }
      const data = await res.json();
      mutate(`${API_URL}/api/campaigns`);
      setCampaignName("");
      setIsOpen(false);
    } catch (err: any) {
      setSubError(err.message || "An error occurred");
    } finally {
      setIsSubmitting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const classes: Record<string, string> = {
      draft: "bg-slate-100 text-slate-700 border-slate-200",
      ready: "bg-green-50 text-green-700 border-green-200",
      scheduled: "bg-blue-50 text-blue-700 border-blue-200",
      sending: "bg-indigo-50 text-indigo-700 border-indigo-200",
      autopilot: "bg-purple-50 text-purple-700 border-purple-200",
      paused: "bg-amber-50 text-amber-700 border-amber-200",
      ended: "bg-red-50 text-red-700 border-red-200",
      stopped: "bg-red-50 text-red-700 border-red-200",
    };
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${
          classes[status.toLowerCase()] || "bg-slate-100 text-slate-700"
        }`}
      >
        {status}
      </span>
    );
  };

  return (
    <div className="p-8 space-y-6 max-w-6xl mx-auto w-full">
      {/* Header section */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Campaigns</h1>
          <p className="text-slate-500 text-sm mt-1">Manage and track your email outreach campaigns</p>
        </div>

        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger className="bg-blue-600 hover:bg-blue-700 text-white gap-2 shadow-sm inline-flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            <Plus className="w-4 h-4" />
            <span>New campaign</span>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <form onSubmit={handleCreate}>
              <DialogHeader>
                <DialogTitle>Create campaign</DialogTitle>
              </DialogHeader>
              <div className="py-4 space-y-3">
                <label className="text-sm font-medium text-slate-700">Campaign name</label>
                <Input
                  placeholder="e.g. My Campaign"
                  value={campaignName}
                  onChange={(e) => setCampaignName(e.target.value)}
                  disabled={isSubmitting}
                  autoFocus
                />
                {subError && <p className="text-sm text-red-600 mt-1">{subError}</p>}
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" className="bg-blue-600 hover:bg-blue-700 text-white" disabled={isSubmitting || !campaignName.trim()}>
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      <span>Creating...</span>
                    </>
                  ) : (
                    <span>Create</span>
                  )}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Campaigns Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
        {isLoading ? (
          <div className="p-12 flex flex-col items-center justify-center text-slate-400 gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            <span className="text-sm">Loading campaigns...</span>
          </div>
        ) : error ? (
          <div className="p-12 text-center text-red-500 font-medium">
            Error loading campaigns. Please ensure the backend is running.
          </div>
        ) : !campaigns || campaigns.length === 0 ? (
          <div className="p-16 text-center space-y-4">
            <div className="mx-auto w-12 h-12 bg-slate-50 border border-slate-200 rounded-full flex items-center justify-center text-slate-400">
              <Mail className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-900 text-lg">No campaigns found</h3>
              <p className="text-slate-500 text-sm mt-1 max-w-sm mx-auto">
                Get started by creating your very first campaign.
              </p>
            </div>
            <Button
              className="bg-blue-600 hover:bg-blue-700 text-white"
              onClick={() => setIsOpen(true)}
            >
              Create campaign
            </Button>
          </div>
        ) : (
          <Table>
            <TableHeader className="bg-slate-50">
              <TableRow>
                <TableHead className="font-semibold text-slate-700">Campaign Name</TableHead>
                <TableHead className="font-semibold text-slate-700">Status</TableHead>
                <TableHead className="font-semibold text-slate-700 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {campaigns.map((camp: any) => (
                <TableRow key={camp.id} className="hover:bg-slate-50/50">
                  <TableCell className="font-medium text-slate-900">
                    <Link
                      href={`/campaigns/${camp.id}`}
                      className="hover:underline hover:text-blue-600 block py-1"
                    >
                      {camp.name}
                    </Link>
                  </TableCell>
                  <TableCell>{getStatusBadge(camp.status || "draft")}</TableCell>
                  <TableCell className="text-right">
                    <Link
                      href={`/campaigns/${camp.id}`}
                      className={buttonVariants({ variant: "ghost", size: "sm", className: "text-slate-600 gap-1 hover:text-blue-600" })}
                    >
                      <span>Open</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
