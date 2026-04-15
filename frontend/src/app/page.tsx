"use client";

import { useEffect, useState } from "react";
import { getAccounts, getCampaigns } from "@/lib/api";
import Link from "next/link";

export default function HomePage() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getAccounts().catch(() => []),
      getCampaigns().catch(() => []),
    ]).then(([accts, camps]) => {
      setAccounts(accts);
      setCampaigns(camps);
      setLoading(false);
    });
  }, []);

  const totalInvited = campaigns.reduce((sum: number, c: any) => sum + (c.stats?.invited || 0), 0);
  const totalConnected = campaigns.reduce((sum: number, c: any) => sum + (c.stats?.connected || 0), 0);
  const activeCampaigns = campaigns.filter((c: any) => c.status === "active").length;

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-slate-500">Loading...</div>;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-800 mb-8">Dashboard</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard label="Linked Accounts" value={accounts.length} color="blue" />
        <StatCard label="Active Campaigns" value={activeCampaigns} color="green" />
        <StatCard label="Total Invited" value={totalInvited} color="indigo" />
        <StatCard label="Total Connected" value={totalConnected} color="emerald" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-700">Recent Campaigns</h2>
            <Link href="/campaigns" className="text-sm text-green-600 hover:text-green-700">View all</Link>
          </div>
          {campaigns.length === 0 ? (
            <p className="text-slate-400 text-sm">No campaigns yet. <Link href="/campaigns" className="text-green-600 underline">Create one</Link></p>
          ) : (
            <div className="space-y-3">
              {campaigns.slice(0, 5).map((c: any) => (
                <Link key={c.id} href={`/campaigns/${c.id}`} className="block p-3 rounded-lg bg-slate-50 hover:bg-slate-100 transition">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-700">{c.name}</span>
                    <StatusBadge status={c.status} />
                  </div>
                  <div className="text-xs text-slate-500 mt-1">
                    {c.stats?.total || 0} contacts &middot; {c.stats?.invited || 0} invited &middot; {c.stats?.connected || 0} connected
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-700">Accounts</h2>
            <Link href="/accounts" className="text-sm text-green-600 hover:text-green-700">Manage</Link>
          </div>
          {accounts.length === 0 ? (
            <p className="text-slate-400 text-sm">No accounts connected. <Link href="/accounts" className="text-green-600 underline">Add one</Link></p>
          ) : (
            <div className="space-y-3">
              {accounts.map((a: any) => (
                <div key={a.id} className="flex items-center justify-between p-3 rounded-lg bg-slate-50">
                  <div>
                    <p className="font-medium text-slate-700">{a.email}</p>
                    <p className="text-xs text-slate-400">Added {new Date(a.created_at).toLocaleDateString()}</p>
                  </div>
                  <StatusBadge status={a.status} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  const colors: Record<string, string> = {
    blue: "bg-blue-50 text-blue-700 border-blue-200",
    green: "bg-green-50 text-green-700 border-green-200",
    indigo: "bg-indigo-50 text-indigo-700 border-indigo-200",
    emerald: "bg-emerald-50 text-emerald-700 border-emerald-200",
  };
  return (
    <div className={`rounded-xl border p-6 ${colors[color]}`}>
      <p className="text-sm font-medium opacity-80">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active: "bg-green-100 text-green-700",
    stopped: "bg-red-100 text-red-700",
    completed: "bg-blue-100 text-blue-700",
    paused: "bg-yellow-100 text-yellow-700",
    login_required: "bg-orange-100 text-orange-700",
    inactive: "bg-slate-100 text-slate-700",
  };
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${styles[status] || "bg-slate-100 text-slate-600"}`}>
      {status.replace("_", " ")}
    </span>
  );
}
