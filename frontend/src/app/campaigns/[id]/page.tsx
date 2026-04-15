"use client";

import { useEffect, useState, use, useCallback } from "react";
import { getCampaign, getLeads, uploadLeads, startCampaign, stopCampaign, deleteLead } from "@/lib/api";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

  useEffect(() => {
    fetchData();
    // Auto-refresh every 30s when campaign is active
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

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
    try {
      await startCampaign(campaignId);
      showToast("Campaign started");
      fetchData();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  };

  const handleStop = async () => {
    try {
      await stopCampaign(campaignId);
      showToast("Campaign stopped");
      fetchData();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  };

  const handleDeleteLead = async (leadId: number) => {
    try {
      await deleteLead(campaignId, leadId);
      showToast("Lead removed");
      fetchData();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-500">Loading...</div>;
  if (!campaign) return <div className="text-center text-red-500 mt-12">Campaign not found</div>;

  const stats = campaign.stats || { total: 0, pending: 0, invited: 0, connected: 0, failed: 0, skipped: 0 };
  const progressPct = stats.total > 0 ? Math.round(((stats.invited + stats.connected) / stats.total) * 100) : 0;

  const filteredLeads = statusFilter === "all"
    ? leads
    : leads.filter((l: any) => l.status === statusFilter);

  return (
    <div>
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium transition-all ${
          toast.type === "success" ? "bg-green-600 text-white" : "bg-red-600 text-white"
        }`}>
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <Link href="/campaigns" className="text-slate-400 hover:text-slate-600 text-xl">&larr;</Link>
        <h1 className="text-2xl font-bold text-slate-800">{campaign.name}</h1>
        <span
          className={`px-3 py-1 rounded-full text-xs font-medium ${
            campaign.status === "active"
              ? "bg-green-100 text-green-700"
              : campaign.status === "completed"
              ? "bg-blue-100 text-blue-700"
              : "bg-red-100 text-red-700"
          }`}
        >
          {campaign.status}
        </span>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        Daily limit: {campaign.daily_limit} | Created: {new Date(campaign.created_at).toLocaleDateString()}
        {campaign.status === "active" && <span className="ml-2 text-green-600">(auto-refreshing every 30s)</span>}
      </p>

      {/* Progress Bar */}
      {stats.total > 0 && (
        <div className="mb-6">
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span>Progress</span>
            <span>{progressPct}% ({stats.invited + stats.connected}/{stats.total})</span>
          </div>
          <div className="w-full bg-slate-200 rounded-full h-2.5">
            <div
              className="bg-green-500 h-2.5 rounded-full transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
          <p className="text-2xl font-bold text-slate-700">{stats.total}</p>
          <p className="text-xs text-slate-500">Total</p>
        </div>
        <div className="bg-white rounded-xl border border-yellow-200 p-4 text-center cursor-pointer hover:bg-yellow-50" onClick={() => setStatusFilter(statusFilter === "pending" ? "all" : "pending")}>
          <p className="text-2xl font-bold text-yellow-600">{stats.pending}</p>
          <p className="text-xs text-slate-500">Pending</p>
        </div>
        <div className="bg-white rounded-xl border border-blue-200 p-4 text-center cursor-pointer hover:bg-blue-50" onClick={() => setStatusFilter(statusFilter === "invited" ? "all" : "invited")}>
          <p className="text-2xl font-bold text-blue-600">{stats.invited}</p>
          <p className="text-xs text-slate-500">Invited</p>
        </div>
        <div className="bg-white rounded-xl border border-green-200 p-4 text-center cursor-pointer hover:bg-green-50" onClick={() => setStatusFilter(statusFilter === "connected" ? "all" : "connected")}>
          <p className="text-2xl font-bold text-green-600">{stats.connected}</p>
          <p className="text-xs text-slate-500">Connected</p>
        </div>
        <div className="bg-white rounded-xl border border-red-200 p-4 text-center cursor-pointer hover:bg-red-50" onClick={() => setStatusFilter(statusFilter === "failed" ? "all" : "failed")}>
          <p className="text-2xl font-bold text-red-600">{stats.failed + stats.skipped}</p>
          <p className="text-xs text-slate-500">Failed</p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3 mb-6">
        {campaign.status === "active" ? (
          <button onClick={handleStop} className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition">
            Stop Campaign
          </button>
        ) : campaign.status !== "completed" ? (
          <button onClick={handleStart} className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition">
            Start Campaign
          </button>
        ) : null}

        <button onClick={() => setShowAddLead(!showAddLead)} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition">
          + Add Lead
        </button>

        <label className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition">
          {uploading ? "Uploading..." : "Upload CSV"}
          <input type="file" accept=".csv" onChange={handleUpload} className="hidden" disabled={uploading} />
        </label>

        <button onClick={fetchData} className="border border-slate-300 text-slate-600 px-4 py-2 rounded-lg text-sm hover:bg-slate-50 transition">
          Refresh
        </button>
      </div>

      {/* Add Lead Form */}
      {showAddLead && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Add a Lead</h3>
          <form onSubmit={handleAddLead} className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-[250px]">
              <label className="block text-xs text-slate-500 mb-1">LinkedIn URL or username</label>
              <input
                type="text"
                value={newLeadUrl}
                onChange={(e) => setNewLeadUrl(e.target.value)}
                required
                placeholder="https://linkedin.com/in/john-doe or john-doe"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="w-48">
              <label className="block text-xs text-slate-500 mb-1">Name (optional)</label>
              <input
                type="text"
                value={newLeadName}
                onChange={(e) => setNewLeadName(e.target.value)}
                placeholder="John Doe"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button type="submit" disabled={addingLead} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 transition">
              {addingLead ? "Adding..." : "Add"}
            </button>
            <button type="button" onClick={() => setShowAddLead(false)} className="text-slate-500 text-sm hover:text-slate-700">
              Cancel
            </button>
          </form>
        </div>
      )}

      {/* Message Template */}
      {campaign.message_template && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6">
          <h3 className="text-sm font-medium text-slate-500 mb-2">Connection Message Template</h3>
          <p className="text-sm text-slate-700 whitespace-pre-wrap">{campaign.message_template}</p>
        </div>
      )}

      {/* Leads Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-700">
            Leads ({filteredLeads.length}{statusFilter !== "all" ? ` ${statusFilter}` : ""})
          </h2>
          {statusFilter !== "all" && (
            <button onClick={() => setStatusFilter("all")} className="text-xs text-blue-600 hover:text-blue-700">
              Show all
            </button>
          )}
        </div>
        {filteredLeads.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <p className="text-lg mb-2">{statusFilter !== "all" ? `No ${statusFilter} leads` : "No leads yet"}</p>
            <p className="text-sm">
              {statusFilter !== "all"
                ? "Try a different filter or add more leads."
                : "Upload a CSV or add leads manually to get started."}
            </p>
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
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          lead.status === "pending"
                            ? "bg-yellow-100 text-yellow-700"
                            : lead.status === "invited"
                            ? "bg-blue-100 text-blue-700"
                            : lead.status === "connected"
                            ? "bg-green-100 text-green-700"
                            : lead.status === "skipped"
                            ? "bg-slate-100 text-slate-600"
                            : "bg-red-100 text-red-700"
                        }`}
                      >
                        {lead.status}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-xs text-slate-500">
                      {lead.last_action_at ? new Date(lead.last_action_at).toLocaleString() : "-"}
                    </td>
                    <td className="px-6 py-3">
                      <button
                        onClick={() => handleDeleteLead(lead.id)}
                        className="text-xs text-red-500 hover:text-red-600"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
