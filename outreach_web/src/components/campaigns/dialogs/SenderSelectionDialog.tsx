import { useState } from "react";
import Link from "next/link";
import useSWR, { mutate } from "swr";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Loader2, Plus, CheckCircle, Trash2, FolderPlus, AtSign, Pencil, Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useApiClient } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// ── Inline editable text field for SenderDialog ──
function InlineEditSender({
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
      <span className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
        <Input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") cancel();
          }}
          className={cn("h-7 text-xs px-2 w-32", inputClassName)}
        />
        <button onClick={(e) => { e.stopPropagation(); commit(); }} className="text-green-600 hover:text-green-700 cursor-pointer">
          <Check className="w-3.5 h-3.5" />
        </button>
        <button onClick={(e) => { e.stopPropagation(); cancel(); }} className="text-slate-400 hover:text-slate-600 cursor-pointer">
          <X className="w-3.5 h-3.5" />
        </button>
      </span>
    );
  }

  return (
    <button
      onClick={(e) => { e.stopPropagation(); setDraft(String(value)); setEditing(true); }}
      className={cn("group flex items-center gap-1 hover:text-blue-600 transition-colors cursor-pointer", className)}
    >
      <span>{value || <span className="italic text-slate-400">{placeholder}</span>}</span>
      <Pencil className="w-2.5 h-2.5 opacity-0 group-hover:opacity-50 transition-opacity" />
    </button>
  );
}

export default function SenderSelectionDialog({
  isOpen,
  onClose,
  senders: initialSenders,
  selectedEmail,
  onSelect,
}: {
  isOpen: boolean;
  onClose: () => void;
  senders: any[];
  selectedEmail: string;
  onSelect: (senderId: number) => void;
}) {
  const { data: sendersData, mutate: mutateSenders } = useSWR<any[]>(
    isOpen ? `${API_URL}/api/senders` : null,
    { fallbackData: initialSenders }
  );
  const senders = sendersData || initialSenders || [];

  const { data: groupsData, mutate: mutateGroups } = useSWR<string[]>(
    isOpen ? `${API_URL}/api/groups` : null
  );
  const allGroups = groupsData || [];
  const { authFetch } = useApiClient();

  const [newGroupName, setNewGroupName] = useState("");
  const [addingGroup, setAddingGroup] = useState(false);
  const [connectingGroup, setConnectingGroup] = useState<string | null>(null);
  const [connectError, setConnectError] = useState("");

  // Bucket senders into groups
  const buckets: Record<string, any[]> = {};
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

  // Render both regular groups and the ungrouped section if there are ungrouped senders
  const groupKeys = [
    ...allGroups,
    ...(buckets[UNGROUPED_KEY].length > 0 ? [UNGROUPED_KEY] : [])
  ];

  // ── patch a sender ──
  const handlePatch = async (id: number, patch: Partial<any>) => {
    const current = senders.find((s) => s.id === id)!;
    const merged = { ...current, ...patch };
    await authFetch(`${API_URL}/api/senders/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        display_name: merged.display_name,
        daily_cap: merged.daily_cap,
        group_name: merged.group_name,
      }),
    });
    mutateSenders(senders.map((s) => (s.id === id ? { ...s, ...patch } : s)), false);
    mutate(`${API_URL}/api/senders`); // sync global SWR cache
  };

  // ── delete sender ──
  const handleDelete = async (id: number) => {
    await authFetch(`${API_URL}/api/senders/${id}`, { method: "DELETE" });
    mutateSenders(senders.filter((s) => s.id !== id), false);
    mutate(`${API_URL}/api/senders`); // sync global SWR cache
  };

  // ── rename group ──
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
    mutateSenders(
      senders.map((s) =>
        s.group_name?.trim() === oldName ? { ...s, group_name: newName.trim() } : s
      ),
      false
    );
    mutate(`${API_URL}/api/senders`); // sync global SWR cache
    mutateGroups();
  };

  // ── connect sender to a specific group ──
  const handleConnectToGroup = async (groupName: string) => {
    setConnectingGroup(groupName);
    setConnectError("");
    try {
      const r = await authFetch(`${API_URL}/api/senders/connect`, { method: "POST" });
      if (!r.ok) {
        const err = await r.json();
        setConnectError(err.detail ?? "Connection failed");
        return;
      }
      const { id } = await r.json();
      
      // Fetch latest and update group
      const current = (await (await authFetch(`${API_URL}/api/senders`)).json()) as any[];
      const newSender = current.find((s) => s.id === id);
      if (newSender) {
        await authFetch(`${API_URL}/api/senders/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            display_name: newSender.display_name,
            daily_cap: newSender.daily_cap,
            group_name: groupName,
          }),
        });
      }
      
      await mutateSenders();
      mutateGroups();
      mutate(`${API_URL}/api/senders`); // sync global SWR cache
      
      // Auto select newly connected sender
      if (newSender) {
        onSelect(Number(id));
      }
    } catch {
      setConnectError("Could not reach backend");
    } finally {
      setConnectingGroup(null);
    }
  };

  // ── create new group ──
  const handleCreateGroup = async () => {
    const name = newGroupName.trim();
    if (!name || allGroups.includes(name)) return;
    await authFetch(`${API_URL}/api/groups`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    mutateGroups();
    setNewGroupName("");
    setAddingGroup(false);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-xl max-h-[85vh] flex flex-col p-6">
        <DialogHeader className="flex flex-row items-center justify-between space-y-0 pb-2 border-b border-slate-100 shrink-0">
          <div>
            <DialogTitle className="text-xl font-bold text-slate-900">Choose Campaign Sender</DialogTitle>
            <p className="text-xs text-slate-500 mt-1">Select a sender for your campaign or manage groups.</p>
          </div>
          <Button
            size="sm"
            onClick={() => setAddingGroup(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white gap-1.5 h-8 text-xs font-semibold cursor-pointer shrink-0"
          >
            <FolderPlus className="w-3.5 h-3.5" />
            New Group
          </Button>
        </DialogHeader>

        {connectError && (
          <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mt-2 shrink-0">
            {connectError}
          </div>
        )}

        {/* Adding New Group Inline Form */}
        {addingGroup && (
          <div className="flex items-center gap-2 p-3 bg-slate-50 border border-blue-100 rounded-xl mt-3 shrink-0">
            <FolderPlus className="w-4 h-4 text-blue-500 shrink-0" />
            <Input
              autoFocus
              placeholder="New group name (e.g. Sales, Marketing)..."
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreateGroup();
                if (e.key === "Escape") { setAddingGroup(false); setNewGroupName(""); }
              }}
              className="h-8 text-xs flex-1 bg-white"
            />
            <Button size="sm" onClick={handleCreateGroup} className="bg-blue-600 hover:bg-blue-700 text-white h-8 text-xs cursor-pointer">
              Create
            </Button>
            <Button size="sm" variant="outline" onClick={() => { setAddingGroup(false); setNewGroupName(""); }} className="h-8 text-xs cursor-pointer">
              Cancel
            </Button>
          </div>
        )}

        {/* Groups and Senders Scrollable Area */}
        <div className="flex-1 overflow-y-auto min-h-0 py-4 space-y-4 pr-1 mt-2">
          {allGroups.length === 0 && !addingGroup ? (
            <div className="border border-dashed border-slate-200 rounded-xl p-8 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center text-blue-500 mx-auto">
                <AtSign className="w-6 h-6" />
              </div>
              <div className="text-sm font-semibold text-slate-800">No Groups Found</div>
              <p className="text-xs text-slate-500 max-w-xs mx-auto">
                Create a group first, then connect Gmail senders inside the group.
              </p>
              <Button
                size="sm"
                onClick={() => setAddingGroup(true)}
                className="bg-blue-600 hover:bg-blue-700 text-white gap-1.5 h-8 text-xs cursor-pointer"
              >
                <FolderPlus className="w-3.5 h-3.5" />
                Create Group
              </Button>
            </div>
          ) : (
            groupKeys.map((g) => {
              const isUngrouped = g === UNGROUPED_KEY;
              const groupSenders = buckets[g] || [];
              const isConnecting = connectingGroup === g;
              return (
                <div key={g} className="border border-slate-100 rounded-xl bg-slate-50/50 overflow-hidden">
                  {/* Group header */}
                  <div className="flex items-center justify-between px-4 py-2 bg-white border-b border-slate-100">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700">
                      {isUngrouped ? (
                        <span className="text-xs font-bold text-slate-500">Ungrouped Senders</span>
                      ) : (
                        <InlineEditSender
                          value={g}
                          onSave={(newName) => handleRenameGroup(g, newName)}
                          className="text-xs font-bold text-slate-700"
                        />
                      )}
                      <span className="text-[10px] font-normal text-slate-400">
                        ({groupSenders.length} sender{groupSenders.length !== 1 ? "s" : ""})
                      </span>
                    </div>

                    {!isUngrouped && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleConnectToGroup(g)}
                        disabled={isConnecting}
                        className="h-7 text-[10px] gap-1 px-2 border-slate-200 hover:border-blue-300 hover:text-blue-600 cursor-pointer"
                      >
                        {isConnecting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                        {isConnecting ? "Connecting..." : "Add sender"}
                      </Button>
                    )}
                  </div>

                  {/* Senders under this group */}
                  <div className="p-3 space-y-2">
                    {groupSenders.length === 0 ? (
                      <div className="text-center py-4 text-xs text-slate-400">
                        No senders in this group.{" "}
                        <button
                          onClick={() => handleConnectToGroup(g)}
                          className="text-blue-500 hover:underline cursor-pointer font-medium"
                        >
                          Connect one
                        </button>
                      </div>
                    ) : (
                      groupSenders.map((sender) => {
                        const isSelected = sender.email === selectedEmail;
                        const initials = sender.email.slice(0, 2).toUpperCase();
                        return (
                          <div
                            key={sender.id}
                            role="button"
                            tabIndex={0}
                            onClick={() => onSelect(Number(sender.id))}
                            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(Number(sender.id)); } }}
                            className={`w-full border rounded-xl p-3 text-left flex items-center justify-between transition-all cursor-pointer ${
                              isSelected
                                ? "border-blue-300 bg-blue-50/60 shadow-sm"
                                : "border-slate-200 bg-white hover:bg-slate-50/80 hover:border-slate-300"
                            }`}
                          >
                            <div className="flex items-center gap-3 min-w-0">
                              {/* Avatar / Initials */}
                              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
                                {initials}
                              </div>
                              <div className="min-w-0">
                                <div className="text-xs font-semibold text-slate-800 truncate">{sender.email}</div>
                                <div className="mt-0.5 text-[10px] text-slate-400">
                                  <InlineEditSender
                                    value={sender.display_name}
                                    placeholder="Add display name..."
                                    onSave={(v) => handlePatch(sender.id, { display_name: v })}
                                  />
                                </div>
                              </div>
                            </div>

                            <div className="flex items-center gap-3 shrink-0">
                              <div className="flex items-center gap-1 text-[10px] text-slate-500 bg-slate-100 rounded-full px-2 py-0.5 font-medium">
                                <span>Cap:</span>
                                <InlineEditSender
                                  value={sender.daily_cap}
                                  onSave={(v) => handlePatch(sender.id, { daily_cap: parseInt(v) || 10 })}
                                  className="font-bold text-slate-700"
                                />
                                <span>/day</span>
                              </div>

                              <div className="flex items-center gap-1.5">
                                {isSelected && <CheckCircle className="w-4 h-4 text-blue-600 shrink-0" />}
                                <button
                                  title="Remove sender"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    if (confirm(`Remove sender ${sender.email}?`)) {
                                      handleDelete(sender.id);
                                    }
                                  }}
                                  className="p-1 rounded text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors cursor-pointer shrink-0"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        <DialogFooter className="flex-row justify-between items-center border-t border-slate-100 pt-4 mt-2 shrink-0">
          <Link
            href="/senders"
            className="text-xs text-slate-500 hover:text-blue-600 underline underline-offset-2 transition-colors"
          >
            Manage senders tab →
          </Link>
          <Button variant="outline" size="sm" onClick={onClose} className="h-8 text-xs cursor-pointer">
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
