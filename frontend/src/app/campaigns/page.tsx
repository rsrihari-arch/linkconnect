"use client";

import { useEffect, useState } from "react";
import { getCampaigns, createCampaign, startCampaign, stopCampaign, deleteCampaign, getAccounts } from "@/lib/api";
import Link from "next/link";

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ account_id: 0, name: "", daily_limit: 20, message_template: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchData = () => {
    getCampaigns().then(setCampaigns).catch(() => {});
    getAccounts().then(setAccounts).catch(() => {});
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.account_id) {
      setError("Please select an account");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await createCampaign(form);
      setForm({ account_id: 0, name: "", daily_limit: 20, message_template: "" });
      setShowForm(false);
      fetchData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStart = async (id: number) => {
    try {
      await startCampaign(id);
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleStop = async (id: number) => {
    try {
      await stopCampaign(id);
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this campaign and all its leads?")) return;
    try {
      await deleteCampaign(id);
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Campaigns</h1>
          <p className="text-sm text-slate-500 mt-1">
            <span className="inline-block w-3 h-3 rounded-full bg-blue-500 mr-1 align-middle"></span> Running
            <span className="inline-block w-3 h-3 rounded-full bg-green-500 mr-1 ml-4 align-middle"></span> Active
            <span className="inline-block w-3 h-3 rounded-full bg-red-500 mr-1 ml-4 align-middle"></span> Stopped
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-green-600 hover:bg-green-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition"
        >
          ADD NEW CAMPAIGN
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-slate-700 mb-4">Create Campaign</h2>
          <form onSubmit={handleCreate} className="space-y-4 max-w-lg">
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Account</label>
              <select
                value={form.account_id}
                onChange={(e) => setForm({ ...form, account_id: Number(e.target.value) })}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
              >
                <option value={0}>Select an account</option>
                {accounts.map((a: any) => (
                  <option key={a.id} value={a.id}>{a.email}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Campaign Name</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="e.g. Q2 Outreach - CTOs"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Daily Connection Limit</label>
              <input
                type="number"
                value={form.daily_limit}
                onChange={(e) => setForm({ ...form, daily_limit: Math.min(30, Number(e.target.value)) })}
                min={1}
                max={30}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
              />
              <p className="text-xs text-slate-400 mt-1">Max 30 per day for safety</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Connection Message (optional)</label>
              <textarea
                value={form.message_template}
                onChange={(e) => setForm({ ...form, message_template: e.target.value })}
                rows={3}
                maxLength={300}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="Hi, I'd love to connect with you..."
              />
              <p className="text-xs text-slate-400 mt-1">{form.message_template.length}/300 characters</p>
            </div>
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={loading}
                className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 transition"
              >
                {loading ? "Creating..." : "Create Campaign"}
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="border border-slate-300 text-slate-600 px-4 py-2 rounded-lg text-sm hover:bg-slate-50 transition"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-slate-200">
        {campaigns.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <p className="text-lg mb-2">No campaigns yet</p>
            <p className="text-sm">Create a campaign to start sending connection requests.</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Campaign Name</th>
                <th className="px-6 py-4">Progress</th>
                <th className="px-6 py-4">Total Contacts</th>
                <th className="px-6 py-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {campaigns.map((c: any) => {
                const stats = c.stats || { total: 0, invited: 0, connected: 0, pending: 0, failed: 0 };
                const invitedPct = stats.total ? Math.round((stats.invited / stats.total) * 100) : 0;
                const connectedPct = stats.total ? Math.round((stats.connected / stats.total) * 100) : 0;
                return (
                  <tr key={c.id} className="hover:bg-slate-50">
                    <td className="px-6 py-4">
                      <span
                        className={`inline-block w-3 h-3 rounded-full ${
                          c.status === "active" ? "bg-green-500" : c.status === "completed" ? "bg-blue-500" : "bg-red-500"
                        }`}
                      ></span>
                    </td>
                    <td className="px-6 py-4">
                      <Link href={`/campaigns/${c.id}`} className="text-sm font-medium text-slate-700 hover:text-green-600">
                        {c.name}
                      </Link>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-green-600 bg-green-50 px-2 py-0.5 rounded">{invitedPct}%</span>
                        <span className="text-xs font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded">{connectedPct}%</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600">
                      <span className="font-semibold">{stats.total} Contacts</span>
                      <div className="text-xs text-slate-400 mt-0.5">
                        {stats.pending} Pending &middot; {stats.invited} Invited &middot; {stats.connected} Connected &middot; {stats.failed} Failed
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex gap-2">
                        {c.status === "active" ? (
                          <button onClick={() => handleStop(c.id)} className="text-sm text-orange-600 hover:text-orange-700 font-medium">
                            Stop
                          </button>
                        ) : c.status !== "completed" ? (
                          <button onClick={() => handleStart(c.id)} className="text-sm text-green-600 hover:text-green-700 font-medium">
                            Start
                          </button>
                        ) : null}
                        <Link href={`/campaigns/${c.id}`} className="text-sm text-blue-600 hover:text-blue-700 font-medium">
                          View
                        </Link>
                        <button onClick={() => handleDelete(c.id)} className="text-sm text-red-500 hover:text-red-600 font-medium">
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
