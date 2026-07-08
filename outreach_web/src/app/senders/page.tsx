"use client";

import { useState, useCallback } from "react";
import useSWR from "swr";
import {
  AtSign,
  Plus,
  Trash2,
  Pencil,
  Check,
  X,
  ChevronDown,
  ChevronRight,
  FolderPlus,
  Loader2,
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

// ─────────────────────────────────────────────
// Inline editable text field
// ─────────────────────────────────────────────
function InlineEdit({
  value,
  onSave,
  placeholder,
  className,
  inputClassName,
}: {
  value: string | number;
  onSave: (v: string) => void;
  placeholder?: string;
  className?: string;
  inputClassName?: string;
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
      <span className="flex items-center gap-1">
        <Input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") cancel();
          }}
          className={cn("h-7 text-xs px-2 w-36", inputClassName)}
        />
        <button onClick={(e) => { e.stopPropagation(); commit(); }} className="text-green-600 hover:text-green-700">
          <Check className="w-3.5 h-3.5" />
        </button>
        <button onClick={(e) => { e.stopPropagation(); cancel(); }} className="text-slate-400 hover:text-slate-600">
          <X className="w-3.5 h-3.5" />
        </button>
      </span>
    );
  }

  return (
    <button
      onClick={(e) => { e.stopPropagation(); setDraft(String(value)); setEditing(true); }}
      className={cn("group flex items-center gap-1 hover:text-blue-600 transition-colors", className)}
    >
      <span>{value || <span className="italic text-slate-400">{placeholder}</span>}</span>
      <Pencil className="w-3 h-3 opacity-0 group-hover:opacity-50 transition-opacity" />
    </button>
  );
}

// ─────────────────────────────────────────────
// Single sender row inside a group
// ─────────────────────────────────────────────
function SenderRow({
  sender,
  onPatch,
  onDelete,
}: {
  sender: Sender;
  onPatch: (id: number, patch: Partial<Sender>) => Promise<void>;
  onDelete: (id: number) => void;
}) {
  const initials = sender.email.slice(0, 2).toUpperCase();

  return (
    <div className="flex items-center gap-4 px-4 py-3 bg-white rounded-xl border border-slate-200 shadow-sm hover:border-blue-200 transition-colors group">
      {/* Avatar */}
      <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
        {initials}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-slate-800 truncate">{sender.email}</span>
        </div>
        <div className="mt-0.5 text-xs text-slate-400">
          <InlineEdit
            value={sender.display_name}
            placeholder="Add display name…"
            onSave={(v) => onPatch(sender.id, { display_name: v })}
          />
        </div>
      </div>

      {/* Daily cap */}
      <div className="flex items-center gap-1 text-xs text-slate-500 shrink-0">
        <span className="text-slate-400">Cap:</span>
        <InlineEdit
          value={sender.daily_cap}
          onSave={(v) => onPatch(sender.id, { daily_cap: parseInt(v) || 10 })}
          className="font-semibold text-slate-700"
        />
        <span className="text-slate-400">/day</span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
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

// ─────────────────────────────────────────────
// Group card (collapsible)
// ─────────────────────────────────────────────
function GroupCard({
  groupName,
  senders,
  onPatch,
  onDelete,
  onRename,
  onConnectToGroup,
  connectingGroup,
  isUngrouped = false,
}: {
  groupName: string;
  senders: Sender[];
  onPatch: (id: number, patch: Partial<Sender>) => Promise<void>;
  onDelete: (id: number) => void;
  onRename: (oldName: string, newName: string) => void;
  onConnectToGroup: (groupName: string) => void;
  connectingGroup: string | null;
  isUngrouped?: boolean;
}) {
  const [open, setOpen] = useState(true);
  const isConnecting = connectingGroup === groupName;

  return (
    <div className="border border-slate-200 rounded-2xl bg-slate-50/60 overflow-hidden">
      {/* Group header */}
      <div className="flex items-center justify-between px-5 py-3 bg-white border-b border-slate-100">
        <div className="flex items-center gap-2 text-sm font-bold text-slate-700">
          <button
            onClick={() => setOpen(!open)}
            className="hover:text-slate-900 transition-colors flex items-center justify-center"
            aria-label="Toggle group"
          >
            {open ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
          </button>
          {isUngrouped ? (
            <span className="text-sm font-bold text-slate-500">{groupName}</span>
          ) : (
            <InlineEdit
              value={groupName}
              onSave={(newName) => onRename(groupName, newName)}
              className="text-sm font-bold text-slate-700 hover:text-slate-900"
            />
          )}
          <span className="text-xs font-normal text-slate-400 ml-1">
            {senders.length} sender{senders.length !== 1 ? "s" : ""}
          </span>
        </div>

        {!isUngrouped && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => onConnectToGroup(groupName)}
            disabled={isConnecting}
            className="h-8 text-xs gap-1.5 border-slate-200 hover:border-blue-300 hover:text-blue-600"
          >
            {isConnecting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
            {isConnecting ? "Connecting…" : "Add sender"}
          </Button>
        )}
      </div>

      {/* Sender list */}
      {open && (
        <div className="p-4 space-y-2">
          {senders.length === 0 ? (
            <div className="text-center py-6 text-slate-400 text-sm">
              No senders in this group yet.{" "}
              <button
                onClick={() => onConnectToGroup(groupName)}
                className="text-blue-500 hover:underline"
              >
                Connect one
              </button>
            </div>
          ) : (
            senders.map((s) => (
              <SenderRow
                key={s.id}
                sender={s}
                onPatch={onPatch}
                onDelete={onDelete}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────
export default function SendersPage() {
  const { data, mutate } = useSWR<Sender[]>(`${API_URL}/api/senders`, fetcher);
  const senders: Sender[] = data ?? [];

  const { data: groupsData, mutate: mutateGroups } = useSWR<string[]>(`${API_URL}/api/groups`, fetcher);

  const [newGroupName, setNewGroupName] = useState("");
  const [addingGroup, setAddingGroup] = useState(false);
  const [connectingGroup, setConnectingGroup] = useState<string | null>(null);
  const [connectError, setConnectError] = useState("");

  const allGroups = groupsData ?? [];

  // Bucket senders into groups
  const buckets: Record<string, Sender[]> = {};
  for (const g of allGroups) buckets[g] = [];
  
  const UNGROUPED_KEY = "__ungrouped__";
  buckets[UNGROUPED_KEY] = [];

  for (const s of senders) {
    const g = s.group_name?.trim();
    if (g && buckets[g]) {
      buckets[g].push(s);
    } else {
      buckets[UNGROUPED_KEY].push(s);
    }
  }

  // Combine regular groups with the ungrouped list if it has items
  const groupKeys = [
    ...allGroups,
    ...(buckets[UNGROUPED_KEY].length > 0 ? [UNGROUPED_KEY] : [])
  ];

  // ── patch a sender ──
  const handlePatch = useCallback(
    async (id: number, patch: Partial<Sender>) => {
      const current = senders.find((s) => s.id === id)!;
      const merged = { ...current, ...patch };
      await fetch(`${API_URL}/api/senders/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          display_name: merged.display_name,
          daily_cap: merged.daily_cap,
          group_name: merged.group_name,
        }),
      });
      mutate(senders.map((s) => (s.id === id ? { ...s, ...patch } : s)), false);
    },
    [senders, mutate]
  );

  // ── delete ──
  const handleDelete = async (id: number) => {
    await fetch(`${API_URL}/api/senders/${id}`, { method: "DELETE" });
    mutate(senders.filter((s) => s.id !== id), false);
  };

  // ── rename group (update all senders in it) ──
  const handleRenameGroup = async (oldName: string, newName: string) => {
    if (!newName.trim() || newName === oldName) return;
    const affected = senders.filter((s) => s.group_name?.trim() === oldName);
    await Promise.all(
      affected.map((s) =>
        fetch(`${API_URL}/api/senders/${s.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ display_name: s.display_name, daily_cap: s.daily_cap, group_name: newName.trim() }),
        })
      )
    );
    mutate(
      senders.map((s) =>
        s.group_name?.trim() === oldName ? { ...s, group_name: newName.trim() } : s
      ),
      false
    );
    mutateGroups();
  };

  // ── connect sender to a specific group ──
  const handleConnectToGroup = async (groupName: string) => {
    setConnectingGroup(groupName);
    setConnectError("");
    try {
      const r = await fetch(`${API_URL}/api/senders/connect`, { method: "POST" });
      if (!r.ok) {
        const err = await r.json();
        setConnectError(err.detail ?? "Connection failed");
        return;
      }
      const { id } = await r.json();
      // assign to this group
      const current = (await (await fetch(`${API_URL}/api/senders`)).json()) as Sender[];
      const newSender = current.find((s) => s.id === id);
      if (newSender) {
        await fetch(`${API_URL}/api/senders/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ display_name: newSender.display_name, daily_cap: newSender.daily_cap, group_name: groupName }),
        });
      }
      await mutate();
      mutateGroups();
    } catch {
      setConnectError("Could not reach backend");
    } finally {
      setConnectingGroup(null);
    }
  };

  // ── create a new group ──
  const handleCreateGroup = async () => {
    const name = newGroupName.trim();
    if (!name || allGroups.includes(name)) return;
    await fetch(`${API_URL}/api/groups`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    mutateGroups();
    setNewGroupName("");
    setAddingGroup(false);
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
            Organize Gmail accounts into groups. Each sender has its own daily cap.
          </p>
        </div>

        <Button
          onClick={() => setAddingGroup(true)}
          className="bg-blue-600 hover:bg-blue-700 text-white gap-2"
        >
          <FolderPlus className="w-4 h-4" />
          New Group
        </Button>
      </div>

      {connectError && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {connectError}
        </div>
      )}

      {/* New group input */}
      {addingGroup && (
        <div className="flex items-center gap-3 p-4 bg-white border border-blue-200 rounded-xl shadow-sm">
          <FolderPlus className="w-5 h-5 text-blue-500 shrink-0" />
          <Input
            autoFocus
            placeholder="Group name (e.g. Personal, Sales, Work)…"
            value={newGroupName}
            onChange={(e) => setNewGroupName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleCreateGroup();
              if (e.key === "Escape") { setAddingGroup(false); setNewGroupName(""); }
            }}
            className="flex-1"
          />
          <Button onClick={handleCreateGroup} className="bg-blue-600 hover:bg-blue-700 text-white">
            Create
          </Button>
          <Button variant="outline" onClick={() => { setAddingGroup(false); setNewGroupName(""); }}>
            Cancel
          </Button>
        </div>
      )}

      {/* Empty state — no groups at all */}
      {allGroups.length === 0 && !addingGroup && (
        <div className="bg-white border border-slate-200 rounded-2xl p-16 text-center space-y-4 shadow-sm">
          <div className="mx-auto w-14 h-14 bg-blue-50 border border-blue-100 rounded-full flex items-center justify-center text-blue-400">
            <AtSign className="w-6 h-6" />
          </div>
          <h3 className="font-semibold text-slate-900 text-lg">No groups yet</h3>
          <p className="text-slate-500 text-sm max-w-sm mx-auto">
            Create a group first (e.g. "Personal", "Sales"), then connect Gmail accounts to it.
          </p>
          <Button
            onClick={() => setAddingGroup(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white gap-2"
          >
            <FolderPlus className="w-4 h-4" />
            Create your first group
          </Button>
        </div>
      )}

      {/* Group cards */}
      {groupKeys.length > 0 && (
        <div className="space-y-4">
          {groupKeys.map((g) => (
            <GroupCard
              key={g}
              groupName={g === UNGROUPED_KEY ? "Ungrouped Senders" : g}
              senders={buckets[g] ?? []}
              onPatch={handlePatch}
              onDelete={handleDelete}
              onRename={handleRenameGroup}
              onConnectToGroup={handleConnectToGroup}
              connectingGroup={connectingGroup}
              isUngrouped={g === UNGROUPED_KEY}
            />
          ))}
        </div>
      )}

      {senders.length > 0 && (
        <p className="text-xs text-slate-400 text-center">
          Click any field to edit inline · Hover a row to see actions
        </p>
      )}
    </div>
  );
}
