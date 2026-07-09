"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import useSWR from "swr";
import {
  AtSign,
  Check,
  ChevronDown,
  ChevronRight,
  FolderPlus,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useApiClient } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const PENDING_SENDER_GROUP_KEY = "pending_sender_group_id";

interface Sender {
  id: number;
  group_id: number;
  email: string;
  display_name: string;
  connected_at: string | null;
  status: string;
  daily_cap: number;
  is_default: boolean;
  sent_today: number;
  daily_cap_remaining: number;
  last_error?: string | null;
}

interface SenderGroup {
  id: number;
  name: string;
  senders: Sender[];
  connected_sender_count: number;
  total_daily_cap: number;
  error_sender_count: number;
}

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

function SenderRow({
  sender,
  onPatch,
  onDelete,
  onSetDefault,
}: {
  sender: Sender;
  onPatch: (id: number, patch: Partial<Sender>) => Promise<void>;
  onDelete: (id: number) => void;
  onSetDefault: (id: number) => void;
}) {
  const initials = sender.email.slice(0, 2).toUpperCase();

  return (
    <div className="flex items-center gap-4 px-4 py-3 bg-white rounded-xl border border-slate-200 shadow-sm hover:border-blue-200 transition-colors group">
      <button
        title={sender.is_default ? "Default sender" : "Set as default sender"}
        onClick={() => !sender.is_default && onSetDefault(sender.id)}
        className={cn(
          "shrink-0 transition-colors",
          sender.is_default
            ? "text-yellow-500 cursor-default"
            : "text-slate-300 hover:text-yellow-400 opacity-0 group-hover:opacity-100"
        )}
      >
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      </button>

      <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
        {initials}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-slate-800 truncate">{sender.email}</span>
          {sender.is_default && (
            <span className="text-[10px] rounded-full px-2 py-0.5 font-semibold bg-yellow-50 text-yellow-700">
              Default
            </span>
          )}
          <span className={cn(
            "text-[10px] rounded-full px-2 py-0.5 font-semibold",
            sender.status === "connected" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
          )}>
            {sender.status}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-1 text-xs text-slate-500 shrink-0">
        <span className="text-slate-400">Cap:</span>
        <InlineEdit
          value={sender.daily_cap}
          onSave={(v) => onPatch(sender.id, { daily_cap: parseInt(v) || 10 })}
          className="font-semibold text-slate-700"
        />
        <span className="text-slate-400">/day</span>
      </div>

      <div className="text-xs text-slate-400 shrink-0">
        {sender.daily_cap_remaining} left
      </div>

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

function GroupCard({
  group,
  onPatchSender,
  onDeleteSender,
  onSetDefault,
  onRename,
  onConnect,
  connectingGroupId,
}: {
  group: SenderGroup;
  onPatchSender: (id: number, patch: Partial<Sender>) => Promise<void>;
  onDeleteSender: (id: number) => void;
  onSetDefault: (id: number) => void;
  onRename: (groupId: number, newName: string) => void;
  onConnect: (groupId: number) => void;
  connectingGroupId: number | null;
}) {
  const [open, setOpen] = useState(true);
  const isConnecting = connectingGroupId === group.id;

  return (
    <div className="border border-slate-200 rounded-2xl bg-slate-50/60 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 bg-white border-b border-slate-100">
        <div className="flex items-center gap-2 text-sm font-bold text-slate-700">
          <button
            onClick={() => setOpen(!open)}
            className="hover:text-slate-900 transition-colors flex items-center justify-center"
            aria-label="Toggle group"
          >
            {open ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
          </button>
          <InlineEdit
            value={group.name}
            onSave={(newName) => onRename(group.id, newName)}
            className="text-sm font-bold text-slate-700 hover:text-slate-900"
          />
          <span className="text-xs font-normal text-slate-400 ml-1">
            {group.connected_sender_count} connected / {group.senders.length} total
          </span>
          <span className="text-xs font-normal text-slate-400">
            {group.total_daily_cap}/day
          </span>
        </div>

        <Button
          size="sm"
          variant="outline"
          onClick={() => onConnect(group.id)}
          disabled={isConnecting}
          className="h-8 text-xs gap-1.5 border-slate-200 hover:border-blue-300 hover:text-blue-600"
        >
          {isConnecting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
          {isConnecting ? "Opening OAuth..." : "Add sender"}
        </Button>
      </div>

      {open && (
        <div className="p-4 space-y-2">
          {group.senders.length === 0 ? (
            <div className="text-center py-6 text-slate-400 text-sm">
              No senders in this group yet.{" "}
              <button onClick={() => onConnect(group.id)} className="text-blue-500 hover:underline">
                Connect one
              </button>
            </div>
          ) : (
            group.senders.map((sender) => (
              <SenderRow
                key={sender.id}
                sender={sender}
                onPatch={onPatchSender}
                onDelete={onDeleteSender}
                onSetDefault={onSetDefault}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

function SendersPageInner() {
  const { data: groups = [], mutate } = useSWR<SenderGroup[]>(`${API_URL}/api/sender-groups`);
  const { authFetch } = useApiClient();
  const searchParams = useSearchParams();

  const [newGroupName, setNewGroupName] = useState("");
  const [addingGroup, setAddingGroup] = useState(false);
  const [connectingGroupId, setConnectingGroupId] = useState<number | null>(null);
  const [connectError, setConnectError] = useState("");

  useEffect(() => {
    if (searchParams.get("oauth")) {
      window.sessionStorage.removeItem(PENDING_SENDER_GROUP_KEY);
      mutate();
    }
  }, [searchParams, mutate]);

  const handlePatchSender = useCallback(
    async (id: number, patch: Partial<Sender>) => {
      try {
        const res = await authFetch(`${API_URL}/api/senders/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          setConnectError(err.detail ?? "Could not update sender");
          return;
        }
        mutate();
      } catch (err: any) {
        setConnectError(err?.message ?? "Could not reach backend");
      }
    },
    [authFetch, mutate]
  );

  const handleSetDefault = useCallback(
    async (id: number) => {
      try {
        const res = await authFetch(`${API_URL}/api/senders/${id}/default`, { method: "PATCH" });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          setConnectError(err.detail ?? "Could not set default sender");
          return;
        }
        mutate();
      } catch (err: any) {
        setConnectError(err?.message ?? "Could not reach backend");
      }
    },
    [authFetch, mutate]
  );

  const handleDeleteSender = async (id: number) => {
    if (!confirm("Remove this sender? It will need OAuth reconnect before it can send again.")) return;
    try {
      const res = await authFetch(`${API_URL}/api/senders/${id}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setConnectError(err.detail ?? "Could not remove sender");
        return;
      }
      mutate();
    } catch (err: any) {
      setConnectError(err?.message ?? "Could not reach backend");
    }
  };

  const handleRenameGroup = async (groupId: number, newName: string) => {
    const name = newName.trim();
    if (!name) return;
    try {
      const res = await authFetch(`${API_URL}/api/sender-groups/${groupId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setConnectError(err.detail ?? "Could not rename group");
        return;
      }
      mutate();
    } catch (err: any) {
      setConnectError(err?.message ?? "Could not reach backend");
    }
  };

  const handleConnectToGroup = async (groupId: number) => {
    setConnectingGroupId(groupId);
    setConnectError("");
    try {
      window.sessionStorage.setItem(PENDING_SENDER_GROUP_KEY, String(groupId));
      const res = await authFetch(`${API_URL}/api/sender-groups/${groupId}/senders/oauth/start`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? "Failed to start Gmail OAuth");
      }
      const { auth_url } = await res.json();
      if (!auth_url) throw new Error("OAuth start did not return an authorization URL");
      window.location.href = auth_url;
    } catch (err: any) {
      window.sessionStorage.removeItem(PENDING_SENDER_GROUP_KEY);
      setConnectError(err?.message ?? "Could not reach backend");
      setConnectingGroupId(null);
    }
  };

  const handleCreateGroup = async () => {
    const name = newGroupName.trim();
    if (!name) return;
    setConnectError("");
    try {
      const res = await authFetch(`${API_URL}/api/sender-groups`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setConnectError(err.detail ?? "Could not create group");
        return;
      }
      setNewGroupName("");
      setAddingGroup(false);
      mutate();
    } catch (err: any) {
      setConnectError(err?.message ?? "Could not reach backend");
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-4xl mx-auto w-full">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <AtSign className="w-7 h-7 text-blue-600" />
            Senders
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Groups own Gmail accounts. Campaigns select a group, and each connected sender keeps its own cap.
          </p>
        </div>

        <Button onClick={() => setAddingGroup(true)} className="bg-blue-600 hover:bg-blue-700 text-white gap-2">
          <FolderPlus className="w-4 h-4" />
          New Group
        </Button>
      </div>

      {connectError && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {connectError}
        </div>
      )}

      {addingGroup && (
        <div className="flex items-center gap-3 p-4 bg-white border border-blue-200 rounded-xl shadow-sm">
          <FolderPlus className="w-5 h-5 text-blue-500 shrink-0" />
          <Input
            autoFocus
            placeholder="Group name"
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

      {groups.length === 0 && !addingGroup ? (
        <div className="bg-white border border-slate-200 rounded-2xl p-16 text-center space-y-4 shadow-sm">
          <div className="mx-auto w-14 h-14 bg-blue-50 border border-blue-100 rounded-full flex items-center justify-center text-blue-400">
            <AtSign className="w-6 h-6" />
          </div>
          <h3 className="font-semibold text-slate-900 text-lg">No groups yet</h3>
          <p className="text-slate-500 text-sm max-w-sm mx-auto">
            Create a group first, then connect one or more Gmail accounts inside it.
          </p>
          <Button onClick={() => setAddingGroup(true)} className="bg-blue-600 hover:bg-blue-700 text-white gap-2">
            <FolderPlus className="w-4 h-4" />
            Create your first group
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          {groups.map((group) => (
            <GroupCard
              key={group.id}
              group={group}
              onPatchSender={handlePatchSender}
              onDeleteSender={handleDeleteSender}
              onSetDefault={handleSetDefault}
              onRename={handleRenameGroup}
              onConnect={handleConnectToGroup}
              connectingGroupId={connectingGroupId}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function SendersPage() {
  return (
    <Suspense fallback={<div className="p-8 text-slate-500 text-sm">Loading...</div>}>
      <SendersPageInner />
    </Suspense>
  );
}
