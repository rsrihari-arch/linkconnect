"use client";

import { useEffect, useState, use, useCallback } from "react";
import {
  getCampaign, getLeads, uploadLeads, startCampaign, stopCampaign, deleteLead,
  getFollowUpSteps, createFollowUpStep, updateFollowUpStep, deleteFollowUpStep, getFollowUpStats,
} from "@/lib/api";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Tab = "leads" | "sequences" | "analytics";

export default function CampaignDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const campaignId = Number(id);

  const [campaign, setCampaign] = useState<any>(null);
  const [leads, setLeads] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" } | null>(null);
  const [showAddLead, setShowAddLead] = useState(false);
  const [newLeadUrl, setNewLeadUrl] = useState("");
  const [newLeadName, setNewLeadName] = useState("");
  const [addingLead, setAddingLead] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [activeTab, setActiveTab] = useState<Tab>("leads");

  // Follow-up state
  const [followUpSteps, setFollowUpSteps] = useState<any[]>([]);
  const [followUpStats, setFollowUpStats] = useState<any[]>([]);
  const [newStepMsg, setNewStepMsg] = useState("");
  const [newStepDays, setNewStepDays] = useState(1);
  const [addingStep, setAddingStep] = useState(false);
  const [editingStepId, setEditingStepId] = useState<number | null>(null);
  const [editMsg, setEditMsg] = useState("");
  const [editDays, setEditDays] = useState(1);

  const showToast = (msg: string, type: "success" | "error" = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchData = useCallback(async () => {
    try {
      const [camp, leadsList] = await Promise.all([
        getCampaign(campaignId),
        getLeads(campaignId),
      ]);
      setCampaign(camp);
      setLeads(leadsList);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  const fetchFollowUps = useCallback(async () => {
    try {
      const [steps, stats] = await Promise.all([
        getFollowUpSteps(campaignId),
        getFollowUpStats(campaignId).catch(() => []),
      ]);
      setFollowUpSteps(steps);
      setFollowUpStats(stats);
    } catch {
      // ignore
    }
  }, [campaignId]);

  useEffect(() => {
    fetchData();
    fetchFollowUps();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData, fetchFollowUps]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const res = await uploadLeads(campaignId, file);
      showToast(res.message);
      fetchData();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const handleAddLead = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLeadUrl.trim()) return;
    setAddingLead(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(
        `${API_BASE}/api/campaigns/${campaignId}/leads?linkedin_url=${encodeURIComponent(newLeadUrl.trim())}&name=${encodeURIComponent(newLeadName.trim())}`,
        { method: "POST", headers }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Failed" }));
        throw new Error(err.detail);
      }
      showToast("Lead added successfully");
      setNewLeadUrl("");
      setNewLeadName("");
      setShowAddLead(false);
      fetchData();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setAddingLead(false);
    }
  };

  const handleStart = async () => {
    try { await startCampaign(campaignId); showToast("Campaign started"); fetchData(); }
    catch (err: any) { showToast(err.message, "error"); }
  };

  const handleStop = async () => {
    try { await stopCampaign(campaignId); showToast("Campaign stopped"); fetchData(); }
    catch (err: any) { showToast(err.message, "error"); }
  };

  const handleDeleteLead = async (leadId: number) => {
    try { await deleteLead(campaignId, leadId); showToast("Lead removed"); fetchData(); }
    catch (err: any) { showToast(err.message, "error"); }
  };

  // Follow-up handlers
  const handleAddStep = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStepMsg.trim()) return;
    setAddingStep(true);
    try {
      await createFollowUpStep(campaignId, { message_template: newStepMsg, delay_days: newStepDays });
      setNewStepMsg("");
      setNewStepDays(1);
      showToast("Follow-up step added");
      fetchFollowUps();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setAddingStep(false);
    }
  };

  const handleUpdateStep = async (stepId: number) => {
    try {
      await updateFollowUpStep(campaignId, stepId, { message_template: editMsg, delay_days: editDays });
      setEditingStepId(null);
      showToast("Step updated");
      fetchFollowUps();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  };

  const handleDeleteStep = async (stepId: number) => {
    if (!confirm("Delete this follow-up step?")) return;
    try {
      await deleteFollowUpStep(campaignId, stepId);
      showToast("Step deleted");
      fetchFollowUps();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-500">Loading...</div>;
  if (!campaign) return <div className="text-center text-red-500 mt-12">Campaign not found</div>;

  const stats = campaign.stats || { total: 0, pending: 0, invited: 0, connected: 0, failed: 0, skipped: 0 };
  const progressPct = stats.total > 0 ? Math.round(((stats.invited + stats.connected) / stats.total) * 100) : 0;
  const filteredLeads = statusFilter === "all" ? leads : leads.filter((l: any) => l.status === statusFilter);

  // Compute follow-up stats (prefer API stats, fallback to computed)
  const totalFollowUpsSent = stats.followups_sent || followUpStats.reduce((sum: number, s: any) => sum + (s.sent || 0), 0);

  return (
    <div>
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium transition-all ${
          toast.type === "success" ? "bg-green-600 text-white" : "bg-red-600 text-white"
        }`}>{toast.msg}</div>
      )}

      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <Link href="/campaigns" className="text-slate-400 hover:text-slate-600 text-xl">&larr;</Link>
        <h1 className="text-2xl font-bold text-slate-800">{campaign.name}</h1>
        <span className={`px-3 py-1 rounded-full text-xs font-medium ${
          campaign.status === "active" ? "bg-green-100 text-green-700"
            : campaign.status === "completed" ? "bg-blue-100 text-blue-700"
            : "bg-red-100 text-red-700"
        }`}>{campaign.status}</span>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        Daily limit: {campaign.daily_limit} | Created: {new Date(campaign.created_at).toLocaleDateString()}
        {campaign.status === "active" && <span className="ml-2 text-green-600">(auto-refreshing)</span>}
      </p>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6">
        <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
          <p className="text-2xl font-bold text-slate-700">{stats.total}</p>
          <p className="text-xs text-slate-500">Total</p>
        </div>
        <div className="bg-white rounded-xl border border-yellow-200 p-4 text-center cursor-pointer hover:bg-yellow-50" onClick={() => { setActiveTab("leads"); setStatusFilter(statusFilter === "pending" ? "all" : "pending"); }}>
          <p className="text-2xl font-bold text-yellow-600">{stats.pending}</p>
          <p className="text-xs text-slate-500">Pending</p>
        </div>
        <div className="bg-white rounded-xl border border-blue-200 p-4 text-center cursor-pointer hover:bg-blue-50" onClick={() => { setActiveTab("leads"); setStatusFilter(statusFilter === "invited" ? "all" : "invited"); }}>
          <p className="text-2xl font-bold text-blue-600">{stats.invited}</p>
          <p className="text-xs text-slate-500">Invited</p>
        </div>
        <div className="bg-white rounded-xl border border-green-200 p-4 text-center cursor-pointer hover:bg-green-50" onClick={() => { setActiveTab("leads"); setStatusFilter(statusFilter === "connected" ? "all" : "connected"); }}>
          <p className="text-2xl font-bold text-green-600">{stats.connected}</p>
          <p className="text-xs text-slate-500">Connected</p>
        </div>
        <div className="bg-white rounded-xl border border-red-200 p-4 text-center cursor-pointer hover:bg-red-50" onClick={() => { setActiveTab("leads"); setStatusFilter(statusFilter === "failed" ? "all" : "failed"); }}>
          <p className="text-2xl font-bold text-red-600">{stats.failed + stats.skipped}</p>
          <p className="text-xs text-slate-500">Failed</p>
        </div>
        <div className="bg-white rounded-xl border border-purple-200 p-4 text-center">
          <p className="text-2xl font-bold text-purple-600">{totalFollowUpsSent}</p>
          <p className="text-xs text-slate-500">Follow-ups Sent</p>
        </div>
      </div>

      {/* Progress Bar */}
      {stats.total > 0 && (
        <div className="mb-6">
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span>Progress</span>
            <span>{progressPct}% ({stats.invited + stats.connected}/{stats.total})</span>
          </div>
          <div className="w-full bg-slate-200 rounded-full h-2.5">
            <div className="bg-green-500 h-2.5 rounded-full transition-all duration-500" style={{ width: `${progressPct}%` }} />
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-3 mb-6">
        {campaign.status === "active" ? (
          <button onClick={handleStop} className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition">Stop Campaign</button>
        ) : campaign.status !== "completed" ? (
          <button onClick={handleStart} className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition">Start Campaign</button>
        ) : null}
        <button onClick={() => { setShowAddLead(!showAddLead); setActiveTab("leads"); }} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition">+ Add Lead</button>
        <label className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition">
          {uploading ? "Uploading..." : "Upload CSV"}
          <input type="file" accept=".csv" onChange={handleUpload} className="hidden" disabled={uploading} />
        </label>
        <button onClick={() => { fetchData(); fetchFollowUps(); }} className="border border-slate-300 text-slate-600 px-4 py-2 rounded-lg text-sm hover:bg-slate-50 transition">Refresh</button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-slate-200">
        {(["leads", "sequences", "analytics"] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
              activeTab === tab
                ? "border-green-600 text-green-700"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {tab === "leads" ? "Campaign Members" : tab === "sequences" ? "Message Sequences" : "Analytics"}
          </button>
        ))}
      </div>

      {/* === LEADS TAB === */}
      {activeTab === "leads" && (
        <>
          {showAddLead && (
            <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6">
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Add a Lead</h3>
              <form onSubmit={handleAddLead} className="flex flex-wrap gap-3 items-end">
                <div className="flex-1 min-w-[250px]">
                  <label className="block text-xs text-slate-500 mb-1">LinkedIn URL or username</label>
                  <input type="text" value={newLeadUrl} onChange={(e) => setNewLeadUrl(e.target.value)} required
                    placeholder="https://linkedin.com/in/john-doe or john-doe"
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div className="w-48">
                  <label className="block text-xs text-slate-500 mb-1">Name (optional)</label>
                  <input type="text" value={newLeadName} onChange={(e) => setNewLeadName(e.target.value)} placeholder="John Doe"
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <button type="submit" disabled={addingLead} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 transition">
                  {addingLead ? "Adding..." : "Add"}
                </button>
                <button type="button" onClick={() => setShowAddLead(false)} className="text-slate-500 text-sm hover:text-slate-700">Cancel</button>
              </form>
            </div>
          )}

          {campaign.message_template && (
            <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6">
              <h3 className="text-sm font-medium text-slate-500 mb-2">Connection Message Template</h3>
              <p className="text-sm text-slate-700 whitespace-pre-wrap">{campaign.message_template}</p>
            </div>
          )}

          <div className="bg-white rounded-xl shadow-sm border border-slate-200">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-700">Leads ({filteredLeads.length}{statusFilter !== "all" ? ` ${statusFilter}` : ""})</h2>
              {statusFilter !== "all" && (
                <button onClick={() => setStatusFilter("all")} className="text-xs text-blue-600 hover:text-blue-700">Show all</button>
              )}
            </div>
            {filteredLeads.length === 0 ? (
              <div className="p-12 text-center text-slate-400">
                <p className="text-lg mb-2">{statusFilter !== "all" ? `No ${statusFilter} leads` : "No leads yet"}</p>
                <p className="text-sm">{statusFilter !== "all" ? "Try a different filter." : "Upload a CSV or add leads manually."}</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      <th className="px-6 py-3">Name</th>
                      <th className="px-6 py-3">LinkedIn URL</th>
                      <th className="px-6 py-3">Status</th>
                      <th className="px-6 py-3">Last Action</th>
                      <th className="px-6 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredLeads.map((lead: any) => (
                      <tr key={lead.id} className="hover:bg-slate-50">
                        <td className="px-6 py-3 text-sm text-slate-700">{lead.name || "-"}</td>
                        <td className="px-6 py-3 text-sm">
                          <a href={lead.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate block max-w-xs">
                            {lead.linkedin_url.replace("https://www.linkedin.com/in/", "").replace("https://www.linkedin.com/", "")}
                          </a>
                        </td>
                        <td className="px-6 py-3">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            lead.status === "pending" ? "bg-yellow-100 text-yellow-700"
                              : lead.status === "invited" ? "bg-blue-100 text-blue-700"
                              : lead.status === "connected" ? "bg-green-100 text-green-700"
                              : lead.status === "skipped" ? "bg-slate-100 text-slate-600"
                              : "bg-red-100 text-red-700"
                          }`}>{lead.status}</span>
                        </td>
                        <td className="px-6 py-3 text-xs text-slate-500">{lead.last_action_at ? new Date(lead.last_action_at).toLocaleString() : "-"}</td>
                        <td className="px-6 py-3">
                          <button onClick={() => handleDeleteLead(lead.id)} className="text-xs text-red-500 hover:text-red-600">Remove</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* === SEQUENCES TAB === */}
      {activeTab === "sequences" && (
        <div className="space-y-6">
          {/* Connection Request Info */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h3 className="text-base font-semibold text-slate-700 mb-3">Connection Request</h3>
            {campaign.message_template ? (
              <div className="bg-slate-50 rounded-lg p-4 text-sm text-slate-700 whitespace-pre-wrap">{campaign.message_template}</div>
            ) : (
              <p className="text-sm text-slate-400">No connection message set. Requests will be sent without a note.</p>
            )}
          </div>

          {/* Follow-up Steps */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-slate-700">Follow-up Messages</h3>
              <span className="text-xs text-slate-400">Sent automatically after connection is accepted</span>
            </div>

            {followUpSteps.length === 0 ? (
              <div className="text-center py-8 text-slate-400">
                <p className="mb-1">No follow-up messages configured</p>
                <p className="text-xs">Add a follow-up below to automatically message people after they connect.</p>
              </div>
            ) : (
              <div className="space-y-3 mb-6">
                {followUpSteps.map((step: any, idx: number) => {
                  const stepStats = followUpStats.find((s: any) => s.step_id === step.id);
                  const isEditing = editingStepId === step.id;

                  return (
                    <div key={step.id} className="border border-slate-200 rounded-lg p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="bg-purple-100 text-purple-700 text-xs font-medium px-2 py-0.5 rounded-full">Step {idx + 1}</span>
                            <span className="text-xs text-slate-500">Send after {step.delay_days} day{step.delay_days > 1 ? "s" : ""} from connection</span>
                            {stepStats && (
                              <span className="text-xs text-green-600 ml-2">{stepStats.sent} sent</span>
                            )}
                          </div>
                          {isEditing ? (
                            <div className="space-y-2">
                              <textarea value={editMsg} onChange={(e) => setEditMsg(e.target.value)} rows={3}
                                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500" />
                              <div className="flex items-center gap-3">
                                <label className="text-xs text-slate-500">Days after connection:</label>
                                <input type="number" min={1} value={editDays} onChange={(e) => setEditDays(Number(e.target.value))}
                                  className="w-16 border border-slate-300 rounded px-2 py-1 text-sm" />
                                <button onClick={() => handleUpdateStep(step.id)} className="text-xs bg-purple-600 text-white px-3 py-1 rounded hover:bg-purple-700">Save</button>
                                <button onClick={() => setEditingStepId(null)} className="text-xs text-slate-500">Cancel</button>
                              </div>
                            </div>
                          ) : (
                            <p className="text-sm text-slate-700 whitespace-pre-wrap">{step.message_template}</p>
                          )}
                        </div>
                        {!isEditing && (
                          <div className="flex gap-2">
                            <button onClick={() => { setEditingStepId(step.id); setEditMsg(step.message_template); setEditDays(step.delay_days); }}
                              className="text-xs text-blue-600 hover:text-blue-700">Edit</button>
                            <button onClick={() => handleDeleteStep(step.id)} className="text-xs text-red-500 hover:text-red-600">Delete</button>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Add new step form */}
            <div className="border-t border-slate-200 pt-4">
              <h4 className="text-sm font-medium text-slate-600 mb-3">Add Follow-up Message</h4>
              <form onSubmit={handleAddStep} className="space-y-3">
                <div>
                  <textarea value={newStepMsg} onChange={(e) => setNewStepMsg(e.target.value)} rows={3} required
                    placeholder="Hi {first_name}, thanks for connecting! I wanted to reach out because..."
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500" />
                  <p className="text-xs text-slate-400 mt-1">
                    Variables: {"{first_name}"}, {"{last_name}"}, {"{name}"}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <label className="text-sm text-slate-600">Send after</label>
                  <input type="number" min={1} value={newStepDays} onChange={(e) => setNewStepDays(Number(e.target.value))}
                    className="w-16 border border-slate-300 rounded px-2 py-1.5 text-sm" />
                  <span className="text-sm text-slate-600">day{newStepDays > 1 ? "s" : ""} from connection</span>
                  <button type="submit" disabled={addingStep || !newStepMsg.trim()}
                    className="ml-auto bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 transition">
                    {addingStep ? "Adding..." : "+ Add Follow-up"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* === ANALYTICS TAB === */}
      {activeTab === "analytics" && (() => {
        const inviteSent = stats.invited + stats.connected;
        const followupsSent = stats.followups_sent || 0;
        const followupsFailed = stats.followups_failed || 0;
        const acceptRate = inviteSent > 0 ? Math.round((stats.connected / inviteSent) * 100) : 0;

        return (
        <div className="space-y-6">
          {/* Overview Cards - 2 rows */}
          <div>
            <h3 className="text-sm font-medium text-slate-500 mb-3 uppercase tracking-wider">Outreach</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-3xl font-bold text-slate-700">{stats.total}</p>
                <p className="text-sm text-slate-500 mt-1">Total Members</p>
              </div>
              <div className="bg-white rounded-xl border border-blue-200 p-5">
                <p className="text-3xl font-bold text-blue-600">{inviteSent}</p>
                <p className="text-sm text-slate-500 mt-1">Contacts Invited</p>
              </div>
              <div className="bg-white rounded-xl border border-green-200 p-5">
                <p className="text-3xl font-bold text-green-600">{stats.connected}</p>
                <p className="text-sm text-slate-500 mt-1">Connected</p>
              </div>
              <div className="bg-white rounded-xl border border-red-200 p-5">
                <p className="text-3xl font-bold text-red-500">{stats.failed + stats.skipped}</p>
                <p className="text-sm text-slate-500 mt-1">Failed / Skipped</p>
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium text-slate-500 mb-3 uppercase tracking-wider">After Connection</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div className="bg-white rounded-xl border border-purple-200 p-5">
                <p className="text-3xl font-bold text-purple-600">{followupsSent}</p>
                <p className="text-sm text-slate-500 mt-1">Follow-up Messages Sent</p>
              </div>
              <div className="bg-white rounded-xl border border-orange-200 p-5">
                <p className="text-3xl font-bold text-orange-500">{followupsFailed}</p>
                <p className="text-sm text-slate-500 mt-1">Follow-ups Failed</p>
              </div>
              <div className="bg-white rounded-xl border border-teal-200 p-5">
                <p className="text-3xl font-bold text-teal-600">{followUpSteps.length}</p>
                <p className="text-sm text-slate-500 mt-1">Sequence Steps</p>
              </div>
            </div>
          </div>

          {/* Full Funnel */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h3 className="text-base font-semibold text-slate-700 mb-5">Campaign Funnel</h3>
            <div className="space-y-4">
              {[
                { label: "Invite Sent", value: inviteSent, base: stats.total, color: "bg-blue-500", desc: `${stats.total > 0 ? Math.round((inviteSent / stats.total) * 100) : 0}% of total` },
                { label: "Connection Accepted", value: stats.connected, base: inviteSent, color: "bg-green-500", desc: `${acceptRate}% accept rate` },
                { label: "Follow-up Messages Sent", value: followupsSent, base: stats.connected, color: "bg-purple-500", desc: `${stats.connected > 0 ? Math.round((followupsSent / stats.connected) * 100) : 0}% of connected` },
              ].map((step) => (
                <div key={step.label}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-600">{step.label}</span>
                    <span className="font-medium">{step.value} <span className="text-slate-400 font-normal">({step.desc})</span></span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-3">
                    <div className={`${step.color} h-3 rounded-full transition-all`} style={{ width: `${step.base > 0 ? Math.min((step.value / step.base) * 100, 100) : 0}%` }} />
                  </div>
                </div>
              ))}
              {/* Failure bar */}
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-600">Failed / Skipped</span>
                  <span className="font-medium">{stats.failed + stats.skipped} <span className="text-slate-400 font-normal">({stats.total > 0 ? Math.round(((stats.failed + stats.skipped) / stats.total) * 100) : 0}% of total)</span></span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-3">
                  <div className="bg-red-400 h-3 rounded-full transition-all" style={{ width: `${stats.total > 0 ? ((stats.failed + stats.skipped) / stats.total) * 100 : 0}%` }} />
                </div>
              </div>
            </div>
          </div>

          {/* Follow-up Step Performance */}
          {followUpStats.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="text-base font-semibold text-slate-700 mb-4">Follow-up Step Performance</h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs font-medium text-slate-500 uppercase">
                      <th className="px-4 py-2">Step</th>
                      <th className="px-4 py-2">Delay</th>
                      <th className="px-4 py-2">Messages Sent</th>
                      <th className="px-4 py-2">Failed</th>
                      <th className="px-4 py-2">Delivery Rate</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {followUpStats.map((s: any) => {
                      const stepTotal = (s.sent || 0) + (s.failed || 0);
                      const deliveryRate = stepTotal > 0 ? Math.round((s.sent / stepTotal) * 100) : 0;
                      return (
                        <tr key={s.step_id}>
                          <td className="px-4 py-3 text-sm font-medium text-slate-700">Step {s.step_order}</td>
                          <td className="px-4 py-3 text-sm text-slate-500">{s.delay_days} day{s.delay_days > 1 ? "s" : ""} after connection</td>
                          <td className="px-4 py-3 text-sm text-green-600 font-medium">{s.sent}</td>
                          <td className="px-4 py-3 text-sm text-red-500">{s.failed}</td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <div className="w-16 bg-slate-100 rounded-full h-2">
                                <div className="bg-green-500 h-2 rounded-full" style={{ width: `${deliveryRate}%` }} />
                              </div>
                              <span className="text-xs text-slate-500">{deliveryRate}%</span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Status Breakdown */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h3 className="text-base font-semibold text-slate-700 mb-4">Status Breakdown</h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {[
                { label: "Pending", value: stats.pending, color: "bg-yellow-500" },
                { label: "Invited", value: stats.invited, color: "bg-blue-500" },
                { label: "Connected", value: stats.connected, color: "bg-green-500" },
                { label: "Failed", value: stats.failed, color: "bg-red-500" },
                { label: "Skipped", value: stats.skipped, color: "bg-slate-400" },
              ].map((item) => (
                <div key={item.label} className="text-center">
                  <div className="flex items-end justify-center gap-1 h-24 mb-2">
                    <div
                      className={`${item.color} rounded-t w-12 transition-all`}
                      style={{ height: `${stats.total > 0 ? Math.max((item.value / stats.total) * 100, 4) : 4}%` }}
                    />
                  </div>
                  <p className="text-lg font-bold text-slate-700">{item.value}</p>
                  <p className="text-xs text-slate-500">{item.label}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
        );
      })()}
    </div>
  );
}
