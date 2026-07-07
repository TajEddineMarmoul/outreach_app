"use client";

import { useState, useCallback } from "react";
import useSWR from "swr";
import {
  AtSign,
  Plus,
  Trash2,
  Star,
  StarOff,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Wifi,
  WifiOff,
  Pencil,
  Check,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface Sender {
  id: number;
  email: string;
  display_name: string;
  token_path: string;
  connected_at: string;
  status: string;
  daily_cap: number;
  is_default: number;
  group_name: string;
}

// ──────────────────────────────────────────────
// Inline editable field
// ──────────────────────────────────────────────
function InlineEdit({
  value,
  onSave,
  placeholder,
  className,
}: {
  value: string | number;
  onSave: (v: string) => void;
  placeholder?: string;
  className?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(value));

  const commit = () => {
    setEditing(false);
    if (draft !== String(value)) onSave(draft);
  };
  const cancel = () => {
    setDraft(String(value));
    setEditing(false);
  };

  if (editing) {
    return (
      <span className={cn("flex items-center gap-1", className)}>
        <Input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") cancel();
          }}
          className="h-7 text-xs px-2 w-40"
        />
        <button onClick={commit} className="text-green-600 hover:text-green-700">
          <Check className="w-3.5 h-3.5" />
        </button>
        <button onClick={cancel} className="text-slate-400 hover:text-slate-600">
          <X className="w-3.5 h-3.5" />
        </button>
      </span>
    );
  }

  return (
    <button
      onClick={() => {
        setDraft(String(value));
        setEditing(true);
      }}
      className={cn(
        "group flex items-center gap-1 text-left hover:text-blue-600 transition-colors",
        className
      )}
    >
      <span>{value || <span className="text-slate-400 italic">{placeholder}</span>}</span>
      <Pencil className="w-3 h-3 opacity-0 group-hover:opacity-60 transition-opacity" />
    </button>
  );
}

// ──────────────────────────────────────────────
// Single sender row
// ──────────────────────────────────────────────
function SenderRow({
  sender,
  onUpdate,
  onDelete,
  onSetDefault,
}: {
  sender: Sender;
  onUpdate: (id: number, patch: Partial<Sender>) => void;
  onDelete: (id: number) => void;
  onSetDefault: (id: number) => void;
}) {
  const initials = sender.email.slice(0, 2).toUpperCase();

  const patchField = useCallback(
    async (patch: Partial<Sender>) => {
      const merged = { ...sender, ...patch };
      await fetch(`${API_URL}/api/senders/${sender.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          display_name: merged.display_name,
          daily_cap: merged.daily_cap,
          group_name: merged.group_name,
        }),
      });
      onUpdate(sender.id, patch);
    },
    [sender, onUpdate]
  );

  return (
    <div className="flex items-center gap-4 px-4 py-3 bg-white rounded-xl border border-slate-200 shadow-sm hover:border-blue-200 transition-colors group">
      {/* Avatar */}
      <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
        {initials}
      </div>

      {/* Email + Display name */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-slate-800 truncate">{sender.email}</span>
          {sender.is_default === 1 && (
            <span className="text-[10px] px-1.5 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded-full font-medium">
              Default
            </span>
          )}
          <span
            className={cn(
              "flex items-center gap-1 text-[10px] font-medium",
              sender.status === "connected" ? "text-emerald-600" : "text-slate-400"
            )}
          >
            {sender.status === "connected" ? (
              <Wifi className="w-3 h-3" />
            ) : (
              <WifiOff className="w-3 h-3" />
            )}
            {sender.status}
          </span>
        </div>
        <div className="flex items-center gap-3 mt-0.5 text-xs text-slate-500">
          <InlineEdit
            value={sender.display_name}
            placeholder="Add display name…"
            onSave={(v) => patchField({ display_name: v })}
          />
        </div>
      </div>

      {/* Daily cap */}
      <div className="flex items-center gap-1.5 text-xs text-slate-600 shrink-0">
        <span className="text-slate-400">Cap:</span>
        <InlineEdit
          value={sender.daily_cap}
          onSave={(v) => patchField({ daily_cap: parseInt(v) || 10 })}
          className="font-semibold text-slate-700"
        />
        <span className="text-slate-400">/day</span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        {sender.is_default !== 1 && (
          <button
            title="Set as default"
            onClick={() => onSetDefault(sender.id)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-amber-500 hover:bg-amber-50 transition-colors"
          >
            <Star className="w-4 h-4" />
          </button>
        )}
        <button
          title="Remove sender"
          onClick={() => onDelete(sender.id)}
          className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────
// Group section (collapsible)
// ──────────────────────────────────────────────
function GroupSection({
  name,
  senders,
  onUpdate,
  onDelete,
  onSetDefault,
  onRename,
}: {
  name: string;
  senders: Sender[];
  onUpdate: (id: number, patch: Partial<Sender>) => void;
  onDelete: (id: number) => void;
  onSetDefault: (id: number) => void;
  onRename: (oldName: string, newName: string) => void;
}) {
  const [open, setOpen] = useState(true);

  return (
    <div className="space-y-2">
      {/* Group header */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider hover:text-slate-700 transition-colors"
        >
          {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          {name === "__ungrouped__" ? "Ungrouped" : (
            <InlineEdit
              value={name}
              placeholder="Group name"
              onSave={(newName) => onRename(name, newName)}
              className="text-xs font-semibold text-slate-500 uppercase tracking-wider"
            />
          )}
          <span className="ml-1 text-slate-400 normal-case font-normal tracking-normal">
            ({senders.length})
          </span>
        </button>
      </div>

      {/* Sender rows */}
      {open && (
        <div className="space-y-2 pl-4">
          {senders.map((s) => (
            <SenderRow
              key={s.id}
              sender={s}
              onUpdate={onUpdate}
              onDelete={onDelete}
              onSetDefault={onSetDefault}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────
// Main page
// ──────────────────────────────────────────────
export default function SendersPage() {
  const { data, mutate } = useSWR<Sender[]>(`${API_URL}/api/senders`, fetcher);
  const senders: Sender[] = data ?? [];

  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState("");

  // ── group senders ──
  const groups: Record<string, Sender[]> = {};
  for (const s of senders) {
    const key = s.group_name?.trim() || "__ungrouped__";
    if (!groups[key]) groups[key] = [];
    groups[key].push(s);
  }
  const groupKeys = Object.keys(groups).sort((a, b) =>
    a === "__ungrouped__" ? 1 : b === "__ungrouped__" ? -1 : a.localeCompare(b)
  );

  // ── handlers ──
  const handleUpdate = useCallback(
    (id: number, patch: Partial<Sender>) => {
      mutate(
        senders.map((s) => (s.id === id ? { ...s, ...patch } : s)),
        false
      );
    },
    [senders, mutate]
  );

  const handleDelete = async (id: number) => {
    await fetch(`${API_URL}/api/senders/${id}`, { method: "DELETE" });
    mutate(senders.filter((s) => s.id !== id), false);
  };

  const handleSetDefault = async (id: number) => {
    await fetch(`${API_URL}/api/senders/${id}/set-default`, { method: "POST" });
    mutate(
      senders.map((s) => ({ ...s, is_default: s.id === id ? 1 : 0 })),
      false
    );
  };

  const handleRenameGroup = async (oldName: string, newName: string) => {
    const affected = senders.filter(
      (s) => (s.group_name?.trim() || "__ungrouped__") === oldName
    );
    await Promise.all(
      affected.map((s) =>
        fetch(`${API_URL}/api/senders/${s.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            display_name: s.display_name,
            daily_cap: s.daily_cap,
            group_name: newName === "__ungrouped__" ? "" : newName,
          }),
        })
      )
    );
    mutate(
      senders.map((s) =>
        (s.group_name?.trim() || "__ungrouped__") === oldName
          ? { ...s, group_name: newName === "__ungrouped__" ? "" : newName }
          : s
      ),
      false
    );
  };

  const handleConnect = async () => {
    setConnecting(true);
    setConnectError("");
    try {
      const r = await fetch(`${API_URL}/api/senders/connect`, { method: "POST" });
      if (!r.ok) {
        const err = await r.json();
        setConnectError(err.detail ?? "Connection failed");
      } else {
        await mutate();
      }
    } catch {
      setConnectError("Could not reach backend");
    } finally {
      setConnecting(false);
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-4xl mx-auto w-full">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <AtSign className="w-7 h-7 text-blue-600" />
            Senders
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Manage Gmail accounts used to send emails. Each sender has its own daily cap.
          </p>
        </div>
        <Button
          onClick={handleConnect}
          disabled={connecting}
          className="bg-blue-600 hover:bg-blue-700 text-white gap-2"
        >
          <Plus className="w-4 h-4" />
          {connecting ? "Connecting…" : "Connect Gmail"}
        </Button>
      </div>

      {connectError && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {connectError}
        </div>
      )}

      {/* Empty state */}
      {senders.length === 0 && !connecting && (
        <div className="bg-white border border-slate-200 rounded-xl p-16 text-center space-y-4 shadow-sm">
          <div className="mx-auto w-14 h-14 bg-blue-50 border border-blue-100 rounded-full flex items-center justify-center text-blue-400">
            <AtSign className="w-6 h-6" />
          </div>
          <h3 className="font-semibold text-slate-900 text-lg">No senders yet</h3>
          <p className="text-slate-500 text-sm max-w-sm mx-auto">
            Connect a Gmail account to start sending. Each account can have its own daily limit and group label.
          </p>
          <Button
            onClick={handleConnect}
            disabled={connecting}
            className="bg-blue-600 hover:bg-blue-700 text-white gap-2 mt-2"
          >
            <Plus className="w-4 h-4" />
            Connect your first Gmail account
          </Button>
        </div>
      )}

      {/* Groups */}
      {groupKeys.length > 0 && (
        <div className="space-y-6">
          {groupKeys.map((key) => (
            <div key={key} className="space-y-2">
              {/* Only show header for named groups */}
              {key !== "__ungrouped__" && (
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    <ChevronDown className="w-3.5 h-3.5" />
                    <InlineEdit
                      value={key}
                      placeholder="Group name"
                      onSave={(newName) => handleRenameGroup(key, newName)}
                      className="text-xs font-semibold text-slate-500 uppercase tracking-wider"
                    />
                    <span className="ml-1 text-slate-400 normal-case font-normal tracking-normal">
                      ({groups[key].length})
                    </span>
                  </div>
                </div>
              )}
              <div className={key !== "__ungrouped__" ? "pl-4 space-y-2" : "space-y-2"}>
                {groups[key].map((s) => (
                  <SenderRow
                    key={s.id}
                    sender={s}
                    onUpdate={handleUpdate}
                    onDelete={handleDelete}
                    onSetDefault={handleSetDefault}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Legend */}
      {senders.length > 0 && (
        <p className="text-xs text-slate-400 text-center pt-2">
          Click any field to edit inline • Hover a row to see actions • Daily cap controls how many emails this account sends per day
        </p>
      )}
    </div>
  );
}
