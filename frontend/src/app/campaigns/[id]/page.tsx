"use client";

import { useEffect, useState, use } from "react";
import { getCampaign, getLeads, uploadLeads, startCampaign, stopCampaign, deleteLead } from "@/lib/api";
import Link from "next/link";

export default function CampaignDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const campaignId = Number(id);

  const [campaign, setCampaign] = useState<any>(null);
  const [leads, setLeads] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");

  const fetchData = async () => {
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
  };

  useEffect(() => {
    fetchData();
  }, [campaignId]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadMsg("");
    try {
      const res = await uploadLeads(campaignId, file);
      setUploadMsg(res.message);
      fetchData();
    } catch (err: any) {
      setUploadMsg(err.message);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const handleStart = async () => {
    try {
      await startCampaign(campaignId);
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleStop = async () => {
    try {
      await stopCampaign(campaignId);
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDeleteLead = async (leadId: number) => {
    try {
      await deleteLead(campaignId, leadId);
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-500">Loading...</div>;
  if (!campaign) return <div className="text-center text-red-500 mt-12">Campaign not found</div>;

  const stats = campaign.stats || { total: 0, pending: 0, invited: 0, connected: 0, failed: 0, skipped: 0 };

  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <Link href="/campaigns" className="text-slate-400 hover:text-slate-600">&larr;</Link>
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
      <p className="text-sm text-slate-500 mb-6">Daily limit: {campaign.daily_limit} | Created: {new Date(campaign.created_at).toLocaleDateString()}</p>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
          <p className="text-2xl font-bold text-slate-700">{stats.total}</p>
          <p className="text-xs text-slate-500">Total</p>
        </div>
        <div className="bg-white rounded-xl border border-yellow-200 p-4 text-center">
          <p className="text-2xl font-bold text-yellow-600">{stats.pending}</p>
          <p className="text-xs text-slate-500">Pending</p>
        </div>
        <div className="bg-white rounded-xl border border-blue-200 p-4 text-center">
          <p className="text-2xl font-bold text-blue-600">{stats.invited}</p>
          <p className="text-xs text-slate-500">Invited</p>
        </div>
        <div className="bg-white rounded-xl border border-green-200 p-4 text-center">
          <p className="text-2xl font-bold text-green-600">{stats.connected}</p>
          <p className="text-xs text-slate-500">Connected</p>
        </div>
        <div className="bg-white rounded-xl border border-red-200 p-4 text-center">
          <p className="text-2xl font-bold text-red-600">{stats.failed + stats.skipped}</p>
          <p className="text-xs text-slate-500">Failed/Skipped</p>
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

        <label className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition">
          {uploading ? "Uploading..." : "Upload CSV"}
          <input type="file" accept=".csv" onChange={handleUpload} className="hidden" disabled={uploading} />
        </label>

        {uploadMsg && <span className="self-center text-sm text-green-600">{uploadMsg}</span>}
      </div>

      {/* Message Template */}
      {campaign.message_template && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6">
          <h3 className="text-sm font-medium text-slate-500 mb-2">Connection Message Template</h3>
          <p className="text-sm text-slate-700 whitespace-pre-wrap">{campaign.message_template}</p>
        </div>
      )}

      {/* Leads Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-700">Leads ({leads.length})</h2>
        </div>
        {leads.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <p className="text-lg mb-2">No leads yet</p>
            <p className="text-sm">Upload a CSV file with LinkedIn profile URLs to get started.</p>
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
                {leads.map((lead: any) => (
                  <tr key={lead.id} className="hover:bg-slate-50">
                    <td className="px-6 py-3 text-sm text-slate-700">{lead.name || "-"}</td>
                    <td className="px-6 py-3 text-sm">
                      <a href={lead.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate block max-w-xs">
                        {lead.linkedin_url.replace("https://www.linkedin.com/in/", "")}
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
