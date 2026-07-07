"use client";

import { useState, useMemo } from "react";
import useSWR, { mutate } from "swr";
import { Users, UserX, Loader2, Folder } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const fetcher = (url: string) => fetch(url).then((r) => {
  if (!r.ok) throw new Error("API call failed");
  return r.json();
});

export default function ContactsPage() {
  const { data: campaigns, isLoading: campaignsLoading } = useSWR(`${API_URL}/api/campaigns`, fetcher);
  const { data: dncList, isLoading: dncLoading } = useSWR(`${API_URL}/api/contacts/dnc`, fetcher);

  const [selectedCampaignId, setSelectedCampaignId] = useState<number | null>(null);
  
  // Auto-select first campaign when campaigns load
  useMemo(() => {
    if (campaigns && campaigns.length > 0 && selectedCampaignId === null) {
      setSelectedCampaignId(campaigns[0].id);
    }
  }, [campaigns, selectedCampaignId]);

  // Fetch recipients for the selected campaign group
  const { data: groupContacts, isLoading: groupLoading } = useSWR(
    selectedCampaignId ? `${API_URL}/api/campaigns/${selectedCampaignId}/recipients` : null,
    fetcher
  );

  const [dncEmail, setDncEmail] = useState("");
  const [submittingDnc, setSubmittingDnc] = useState(false);

  const handleAddDnc = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dncEmail.trim()) return;
    setSubmittingDnc(true);
    try {
      const res = await fetch(`${API_URL}/api/contacts/dnc`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: dncEmail.trim() }),
      });
      if (!res.ok) throw new Error("Failed to add to DNC");
      mutate(`${API_URL}/api/contacts/dnc`);
      setDncEmail("");
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSubmittingDnc(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const classes: Record<string, string> = {
      approved: "bg-green-50 text-green-700 border-green-200",
      pending: "bg-slate-100 text-slate-700 border-slate-200",
      rejected: "bg-red-50 text-red-700 border-red-200",
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
      <div>
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Contacts</h1>
        <p className="text-slate-500 text-sm mt-1">Manage contact groups and block lists</p>
      </div>

      <Tabs defaultValue="groups" className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="groups" className="gap-2">
            <Users className="w-4 h-4" />
            <span>Contact Groups</span>
          </TabsTrigger>
          <TabsTrigger value="dnc" className="gap-2">
            <UserX className="w-4 h-4" />
            <span>Do Not Contact (DNC)</span>
          </TabsTrigger>
        </TabsList>

        {/* 1. Contact Groups Tab */}
        <TabsContent value="groups" className="pt-4">
          {campaignsLoading ? (
            <div className="p-12 flex flex-col items-center justify-center text-slate-400 gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
              <span className="text-sm">Loading contact groups...</span>
            </div>
          ) : !campaigns || campaigns.length === 0 ? (
            <div className="bg-white border border-slate-200 rounded-xl p-16 text-center space-y-3 shadow-sm">
              <div className="mx-auto w-12 h-12 bg-slate-50 border border-slate-200 rounded-full flex items-center justify-center text-slate-400">
                <Users className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-slate-900 text-lg">No contact groups found</h3>
              <p className="text-slate-500 text-sm max-w-sm mx-auto">
                Create a campaign and import contacts via CSV or Google Sheets to see your contact groups here.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              {/* Left Column: Groups List */}
              <div className="md:col-span-1 space-y-2">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider px-2 mb-3">Groups</h3>
                <div className="space-y-1">
                  {campaigns.map((c: any) => {
                    const active = c.id === selectedCampaignId;
                    return (
                      <button
                        key={c.id}
                        onClick={() => setSelectedCampaignId(c.id)}
                        className={`w-full text-left px-3 py-2.5 rounded-lg flex items-center justify-between border transition-all ${
                          active
                            ? "bg-blue-50 border-blue-200 text-blue-800 font-medium"
                            : "bg-white border-slate-100 hover:bg-slate-50 text-slate-700 hover:text-slate-900"
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Folder className={`w-4 h-4 shrink-0 ${active ? "text-blue-600" : "text-slate-400"}`} />
                          <span className="truncate text-sm">{c.name}</span>
                        </div>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          active ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-500"
                        }`}>
                          {c.recipient_count || 0}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Right Column: Group Contacts Table */}
              <div className="md:col-span-3 bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm h-fit">
                {groupLoading ? (
                  <div className="p-12 flex flex-col items-center justify-center text-slate-400 gap-2">
                    <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                    <span className="text-sm">Loading group contacts...</span>
                  </div>
                ) : !groupContacts || groupContacts.length === 0 ? (
                  <div className="p-16 text-center space-y-3">
                    <div className="mx-auto w-12 h-12 bg-slate-50 border border-slate-200 rounded-full flex items-center justify-center text-slate-400">
                      <Users className="w-5 h-5" />
                    </div>
                    <h3 className="font-semibold text-slate-900 text-lg">No contacts in this group</h3>
                    <p className="text-slate-500 text-sm max-w-sm mx-auto">
                      Go to the campaign editor to import your contacts via CSV or Google Sheet.
                    </p>
                  </div>
                ) : (
                  <div>
                    <div className="px-6 py-4 border-b border-slate-150 bg-slate-50 flex items-center justify-between">
                      <h4 className="font-bold text-slate-800 text-sm">
                        Showing {groupContacts.length} contacts
                      </h4>
                    </div>
                    <Table>
                      <TableHeader className="bg-slate-50">
                        <TableRow>
                          <TableHead className="font-semibold text-slate-700">Email</TableHead>
                          <TableHead className="font-semibold text-slate-700">First Name</TableHead>
                          <TableHead className="font-semibold text-slate-700">Company Name</TableHead>
                          <TableHead className="font-semibold text-slate-700">Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {groupContacts.map((c: any) => (
                          <TableRow key={c.id}>
                            <TableCell className="font-semibold text-slate-900">{c.email}</TableCell>
                            <TableCell className="text-slate-700">{c.first_name}</TableCell>
                            <TableCell className="text-slate-700">{c.company_name || "Unknown"}</TableCell>
                            <TableCell>{getStatusBadge(c.status || "pending")}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>
            </div>
          )}
        </TabsContent>

        {/* 2. DNC Tab */}
        <TabsContent value="dnc" className="pt-4 space-y-6">
          {/* Add DNC Form */}
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm max-w-md">
            <h3 className="font-bold text-slate-800 text-sm mb-3">Add email to DNC</h3>
            <form onSubmit={handleAddDnc} className="flex gap-2">
              <Input
                type="email"
                placeholder="e.g. competitor@domain.com"
                value={dncEmail}
                onChange={(e) => setDncEmail(e.target.value)}
                disabled={submittingDnc}
                required
              />
              <Button type="submit" className="bg-slate-800 hover:bg-slate-900 text-white shrink-0" disabled={submittingDnc}>
                {submittingDnc ? "Adding..." : "Add to DNC"}
              </Button>
            </form>
          </div>

          {/* DNC List Table */}
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
            {dncLoading ? (
              <div className="p-12 flex flex-col items-center justify-center text-slate-400 gap-2">
                <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                <span className="text-sm">Loading DNC list...</span>
              </div>
            ) : !dncList || dncList.length === 0 ? (
              <div className="p-16 text-center space-y-3">
                <div className="mx-auto w-12 h-12 bg-slate-50 border border-slate-200 rounded-full flex items-center justify-center text-slate-400">
                  <UserX className="w-5 h-5" />
                </div>
                <h3 className="font-semibold text-slate-900 text-lg">No DNC emails found</h3>
                <p className="text-slate-500 text-sm max-w-sm mx-auto">
                  Add competitor or unsubscribed emails to block list.
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader className="bg-slate-50">
                  <TableRow>
                    <TableHead className="font-semibold text-slate-700">Blocked Email Address</TableHead>
                    <TableHead className="font-semibold text-slate-700">Date Added</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {dncList.map((d: any, idx: number) => (
                    <TableRow key={idx}>
                      <TableCell className="font-mono text-slate-800 font-semibold">{d.email}</TableCell>
                      <TableCell className="text-slate-500 text-xs">
                        {d.created_at ? new Date(d.created_at).toLocaleDateString() : "unknown"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
