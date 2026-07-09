"use client";

import useSWR from "swr";
import { BarChart2, Mail, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export default function AnalyticsPage() {
  const { data: logs, error, isLoading } = useSWR(`${API_URL}/api/logs`);

  // Compute Stats
  const total = logs?.length || 0;
  const successes = logs?.filter((l: any) => l.status === "success" || !l.error_message).length || 0;
  const failures = total - successes;

  return (
    <div className="p-8 space-y-6 max-w-6xl mx-auto w-full">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Analytics</h1>
        <p className="text-slate-500 text-sm mt-1">Monitor sending performance and view logs</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Attempts</CardTitle>
            <Mail className="w-4 h-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-slate-900">{total}</div>
            <p className="text-xs text-slate-400 mt-1">Emails dispatched globally</p>
          </CardContent>
        </Card>

        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Successes</CardTitle>
            <CheckCircle2 className="w-4 h-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-slate-900">{successes}</div>
            <p className="text-xs text-slate-400 mt-1">Successfully delivered emails</p>
          </CardContent>
        </Card>

        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Bounces / Errors</CardTitle>
            <XCircle className="w-4 h-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-slate-900">{failures}</div>
            <p className="text-xs text-slate-400 mt-1">Failed delivery attempts</p>
          </CardContent>
        </Card>
      </div>

      {/* Logs Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
          <h3 className="font-bold text-sm text-slate-800 flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-slate-500" />
            <span>Sending Logs</span>
          </h3>
        </div>

        {isLoading ? (
          <div className="p-12 flex flex-col items-center justify-center text-slate-400 gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            <span className="text-sm">Loading logs...</span>
          </div>
        ) : error ? (
          <div className="p-12 text-center text-red-500 font-medium">
            Error loading logs. Check that the FastAPI backend is running.
          </div>
        ) : !logs || logs.length === 0 ? (
          <div className="p-16 text-center space-y-3">
            <div className="mx-auto w-12 h-12 bg-slate-50 border border-slate-200 rounded-full flex items-center justify-center text-slate-400">
              <Mail className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-900 text-lg">No attempts recorded</h3>
            <p className="text-slate-500 text-sm max-w-sm mx-auto">
              Sending logs will appear here as soon as campaigns start transmitting.
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader className="bg-slate-50">
              <TableRow>
                <TableHead className="font-semibold text-slate-700">Recipient</TableHead>
                <TableHead className="font-semibold text-slate-700">Subject</TableHead>
                <TableHead className="font-semibold text-slate-700">Date/Time</TableHead>
                <TableHead className="font-semibold text-slate-700">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.map((l: any, idx: number) => {
                const isSuccess = l.status === "success" || !l.error_message;
                return (
                  <TableRow key={idx}>
                    <TableCell className="font-semibold text-slate-900">{l.email || l.contact_email}</TableCell>
                    <TableCell className="text-slate-700 max-w-xs truncate">{l.subject || l.sent_subject}</TableCell>
                    <TableCell className="text-slate-500 text-xs">
                      {l.created_at ? new Date(l.created_at).toLocaleString() : "unknown"}
                    </TableCell>
                    <TableCell>
                      {isSuccess ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-green-50 text-green-700 border border-green-200">
                          Success
                        </span>
                      ) : (
                        <span
                          className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200 cursor-pointer"
                          title={l.error_message}
                        >
                          Error
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
