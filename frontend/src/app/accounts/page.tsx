"use client";

import { useEffect, useState } from "react";
import { getAccounts, createAccount, createAccountWithCookies, deleteAccount, loginAccount, submitVerificationCode } from "@/lib/api";

type AddMethod = "cookies" | "password";

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [method, setMethod] = useState<AddMethod>("cookies");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [cookies, setCookies] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [verifyCode, setVerifyCode] = useState<Record<number, string>>({});
  const [verifyLoading, setVerifyLoading] = useState<number | null>(null);
  const [loginLoading, setLoginLoading] = useState<number | null>(null);

  const fetchAccounts = () => getAccounts().then(setAccounts).catch(() => {});

  useEffect(() => {
    fetchAccounts();
  }, []);

  // Auto-poll when any account is verifying or login_required
  useEffect(() => {
    const hasVerifying = accounts.some((a: any) => a.status === "verifying" || a.status === "login_required");
    if (!hasVerifying) return;
    const interval = setInterval(fetchAccounts, 5000);
    return () => clearInterval(interval);
  }, [accounts]);

  const handleLogin = async (id: number) => {
    setLoginLoading(id);
    try {
      await loginAccount(id);
      fetchAccounts();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoginLoading(null);
    }
  };

  const handleVerifyCode = async (id: number) => {
    const code = verifyCode[id]?.trim();
    if (!code) return;
    setVerifyLoading(id);
    try {
      await submitVerificationCode(id, code);
      setVerifyCode((prev) => ({ ...prev, [id]: "" }));
      fetchAccounts();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setVerifyLoading(null);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (method === "cookies") {
        await createAccountWithCookies(email, cookies);
      } else {
        await createAccount(email, password);
      }
      setEmail("");
      setPassword("");
      setCookies("");
      setShowForm(false);
      fetchAccounts();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this account and all its campaigns?")) return;
    try {
      await deleteAccount(id);
      fetchAccounts();
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold text-slate-800">LinkedIn Accounts</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
        >
          + Add Account
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-slate-700 mb-4">Connect LinkedIn Account</h2>

          {/* Method Toggle */}
          <div className="flex gap-2 mb-5">
            <button
              onClick={() => setMethod("cookies")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                method === "cookies"
                  ? "bg-green-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              Paste Cookies (Recommended)
            </button>
            <button
              onClick={() => setMethod("password")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                method === "password"
                  ? "bg-green-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              Email &amp; Password
            </button>
          </div>

          <form onSubmit={handleCreate} className="space-y-4 max-w-xl">
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">LinkedIn Email or Phone Number</label>
              <input
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="email@example.com or +91 98765 43210"
              />
            </div>

            {method === "cookies" ? (
              <>
                <div>
                  <label className="block text-sm font-medium text-slate-600 mb-1">LinkedIn Cookies</label>
                  <textarea
                    value={cookies}
                    onChange={(e) => setCookies(e.target.value)}
                    required
                    rows={5}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-green-500"
                    placeholder='Paste your LinkedIn cookies here (JSON array or "name=value; name2=value2" format)'
                  />
                </div>
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
                  <p className="font-semibold mb-2">How to get your LinkedIn cookies:</p>
                  <ol className="list-decimal list-inside space-y-1 text-blue-700">
                    <li>Open <strong>linkedin.com</strong> in Chrome and make sure you&apos;re logged in</li>
                    <li>Press <strong>F12</strong> to open DevTools</li>
                    <li>Go to <strong>Application</strong> tab &rarr; <strong>Cookies</strong> &rarr; <strong>linkedin.com</strong></li>
                    <li>Find the cookie named <strong>li_at</strong> and copy its value</li>
                    <li>Paste here as: <code className="bg-blue-100 px-1 rounded">li_at=YOUR_VALUE</code></li>
                  </ol>
                  <p className="mt-2 text-xs text-blue-600">
                    Or use a browser extension like &quot;EditThisCookie&quot; to export all cookies as JSON.
                  </p>
                </div>
              </>
            ) : (
              <>
                <div>
                  <label className="block text-sm font-medium text-slate-600 mb-1">Password</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                    placeholder="Your LinkedIn password"
                  />
                </div>
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-xs text-yellow-700">
                  <p className="font-semibold mb-1">How it works:</p>
                  <ol className="list-decimal list-inside space-y-0.5">
                    <li>Save your account with email &amp; password</li>
                    <li>Click &quot;Login&quot; on the account row &mdash; the worker will attempt to log in</li>
                    <li>LinkedIn will send a verification code to your email</li>
                    <li>Enter the code in the input that appears next to the account</li>
                    <li>Once verified, the account becomes active</li>
                  </ol>
                </div>
              </>
            )}

            {error && <p className="text-red-500 text-sm">{error}</p>}
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={loading}
                className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 transition"
              >
                {loading ? "Connecting..." : method === "cookies" ? "Connect Account" : "Save Account"}
              </button>
              <button
                type="button"
                onClick={() => { setShowForm(false); setError(""); }}
                className="border border-slate-300 text-slate-600 px-4 py-2 rounded-lg text-sm hover:bg-slate-50 transition"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-slate-200">
        {accounts.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <p className="text-lg mb-2">No accounts connected</p>
            <p className="text-sm">Click &quot;Add Account&quot; to connect your LinkedIn account.</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                <th className="px-6 py-4">Email / Phone</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Added</th>
                <th className="px-6 py-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {accounts.map((a: any) => (
                <tr key={a.id} className="hover:bg-slate-50">
                  <td className="px-6 py-4 text-sm font-medium text-slate-700">{a.email}</td>
                  <td className="px-6 py-4">
                    <span
                      className={`px-2 py-1 rounded-full text-xs font-medium ${
                        a.status === "active"
                          ? "bg-green-100 text-green-700"
                          : a.status === "verifying"
                          ? "bg-amber-100 text-amber-700"
                          : a.status === "login_required"
                          ? "bg-orange-100 text-orange-700"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {a.status === "active"
                        ? "Active"
                        : a.status === "verifying"
                        ? "Awaiting Code"
                        : a.status === "login_required"
                        ? "Login Required"
                        : a.status}
                    </span>
                    {a.login_error && (
                      <p className="text-xs text-red-500 mt-1 max-w-xs">{a.login_error}</p>
                    )}
                    {a.status === "verifying" && (
                      <div className="mt-2 flex items-center gap-2">
                        <input
                          type="text"
                          placeholder="Enter code"
                          value={verifyCode[a.id] || ""}
                          onChange={(e) => setVerifyCode((prev) => ({ ...prev, [a.id]: e.target.value }))}
                          onKeyDown={(e) => e.key === "Enter" && handleVerifyCode(a.id)}
                          className="border border-slate-300 rounded px-2 py-1 text-sm w-28 focus:outline-none focus:ring-2 focus:ring-amber-400"
                        />
                        <button
                          onClick={() => handleVerifyCode(a.id)}
                          disabled={verifyLoading === a.id}
                          className="bg-amber-500 hover:bg-amber-600 text-white px-3 py-1 rounded text-xs font-medium disabled:opacity-50"
                        >
                          {verifyLoading === a.id ? "..." : "Verify"}
                        </button>
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-500">
                    {new Date(a.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 flex items-center gap-3">
                    {a.status === "login_required" && (
                      <button
                        onClick={() => handleLogin(a.id)}
                        disabled={loginLoading === a.id}
                        className="text-sm text-green-600 hover:text-green-700 font-medium disabled:opacity-50"
                      >
                        {loginLoading === a.id ? "Starting..." : "Login"}
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(a.id)}
                      className="text-sm text-red-500 hover:text-red-600 font-medium"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
