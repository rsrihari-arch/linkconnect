"use client";

import { useEffect, useState } from "react";
import { getAccounts, createAccount, createAccountWithCookies, deleteAccount, loginAccount, submitVerificationCode, refreshAccountCookies } from "@/lib/api";

type AddMethod = "cookies" | "password";

const JS_SNIPPET = `copy(document.cookie.match(/li_at=([^;]+)/)?.[1])`;

function CookieInstructions({ onCopied }: { onCopied: boolean; }) {
  return null; // unused, keeping for ref
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [method, setMethod] = useState<AddMethod>("cookies");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [cookieValue, setCookieValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  // Per-account state
  const [verifyCode, setVerifyCode] = useState<Record<number, string>>({});
  const [verifyLoading, setVerifyLoading] = useState<number | null>(null);
  const [loginLoading, setLoginLoading] = useState<number | null>(null);
  const [refreshingId, setRefreshingId] = useState<number | null>(null);
  const [refreshValue, setRefreshValue] = useState<Record<number, string>>({});
  const [refreshCopied, setRefreshCopied] = useState<Record<number, boolean>>({});
  const [refreshLoading, setRefreshLoading] = useState<number | null>(null);

  const fetchAccounts = () => getAccounts().then(setAccounts).catch(() => {});

  useEffect(() => { fetchAccounts(); }, []);

  useEffect(() => {
    const hasVerifying = accounts.some((a: any) => a.status === "verifying");
    const hasLoginRequired = accounts.some((a: any) => a.status === "login_required");
    if (!hasVerifying && !hasLoginRequired) return;
    const interval = setInterval(fetchAccounts, hasVerifying ? 2000 : 5000);
    return () => clearInterval(interval);
  }, [accounts]);

  const handleCopySnippet = () => {
    navigator.clipboard.writeText(JS_SNIPPET);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleCopySnippetForRefresh = (id: number) => {
    navigator.clipboard.writeText(JS_SNIPPET);
    setRefreshCopied((prev) => ({ ...prev, [id]: true }));
    setTimeout(() => setRefreshCopied((prev) => ({ ...prev, [id]: false })), 2500);
  };

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

  const handleRefreshCookies = async (id: number, email: string) => {
    const val = refreshValue[id]?.trim();
    if (!val) return;
    setRefreshLoading(id);
    try {
      await refreshAccountCookies(id, email, val);
      setRefreshingId(null);
      setRefreshValue((prev) => ({ ...prev, [id]: "" }));
      fetchAccounts();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setRefreshLoading(null);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (method === "cookies") {
        await createAccountWithCookies(email, cookieValue);
      } else {
        await createAccount(email, password);
      }
      setEmail(""); setPassword(""); setCookieValue("");
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

          <div className="flex gap-2 mb-5">
            <button
              onClick={() => setMethod("cookies")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                method === "cookies" ? "bg-green-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              Session Cookie <span className="ml-1 text-xs opacity-75">(recommended)</span>
            </button>
            <button
              onClick={() => setMethod("password")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                method === "password" ? "bg-green-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              Email &amp; Password
            </button>
          </div>

          <form onSubmit={handleCreate} className="space-y-4 max-w-xl">
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">LinkedIn Email</label>
              <input
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="your@email.com"
              />
            </div>

            {method === "cookies" ? (
              <>
                {/* Step-by-step instructions */}
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
                  <p className="text-sm font-semibold text-slate-700 mb-3">3 steps to connect — takes 30 seconds</p>
                  <div className="space-y-3">
                    <div className="flex gap-3 items-start">
                      <span className="flex-shrink-0 w-6 h-6 rounded-full bg-green-600 text-white text-xs flex items-center justify-center font-bold">1</span>
                      <p className="text-sm text-slate-600">
                        Open <strong>linkedin.com</strong> in your browser and make sure you&apos;re logged in
                      </p>
                    </div>
                    <div className="flex gap-3 items-start">
                      <span className="flex-shrink-0 w-6 h-6 rounded-full bg-green-600 text-white text-xs flex items-center justify-center font-bold">2</span>
                      <div className="flex-1">
                        <p className="text-sm text-slate-600 mb-2">
                          Press <kbd className="bg-slate-200 px-1.5 py-0.5 rounded text-xs font-mono">F12</kbd> → open the <strong>Console</strong> tab → paste this command and press Enter
                        </p>
                        <div className="flex items-center gap-2 bg-slate-900 rounded-lg px-3 py-2">
                          <code className="text-green-400 text-xs flex-1 font-mono">{JS_SNIPPET}</code>
                          <button
                            type="button"
                            onClick={handleCopySnippet}
                            className="flex-shrink-0 bg-slate-700 hover:bg-slate-600 text-white text-xs px-2 py-1 rounded transition"
                          >
                            {copied ? "Copied!" : "Copy"}
                          </button>
                        </div>
                        <p className="text-xs text-slate-500 mt-1">This copies your session token to clipboard — it never leaves your browser</p>
                      </div>
                    </div>
                    <div className="flex gap-3 items-start">
                      <span className="flex-shrink-0 w-6 h-6 rounded-full bg-green-600 text-white text-xs flex items-center justify-center font-bold">3</span>
                      <p className="text-sm text-slate-600">Come back here and paste below</p>
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-600 mb-1">Paste your session token here</label>
                  <input
                    type="text"
                    value={cookieValue}
                    onChange={(e) => setCookieValue(e.target.value)}
                    required
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-green-500"
                    placeholder="Paste the copied value here..."
                  />
                  <p className="text-xs text-slate-400 mt-1">Accepts raw token, <code>li_at=...</code> format, or full cookie string</p>
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
                  <p className="font-semibold mb-1">Note:</p>
                  <p>LinkedIn may send a verification code to your phone or email when logging in from a new location. You&apos;ll be able to enter it after clicking Login.</p>
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
                <th className="px-6 py-4">Email</th>
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
                      {a.status === "active" ? "Active"
                        : a.status === "verifying" ? "Awaiting Code"
                        : a.status === "login_required" ? "Login Required"
                        : a.status}
                    </span>
                    {a.login_error && (
                      <p className="text-xs text-red-500 mt-1 max-w-xs">{a.login_error}</p>
                    )}
                    {(a.status === "verifying") && (
                      <div className="mt-2 bg-amber-50 border border-amber-300 rounded-lg p-3">
                        <p className="text-xs font-semibold text-amber-800 mb-1">Waiting for verification code</p>
                        <p className="text-xs text-amber-700 mb-2">
                          Check LinkedIn app → tap &quot;Yes, it&apos;s me&quot; — OR enter the OTP from your email/SMS
                        </p>
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            placeholder="Enter OTP code"
                            value={verifyCode[a.id] || ""}
                            onChange={(e) => setVerifyCode((prev) => ({ ...prev, [a.id]: e.target.value.replace(/\D/g, "").slice(0, 8) }))}
                            onKeyDown={(e) => e.key === "Enter" && handleVerifyCode(a.id)}
                            className="border border-amber-400 rounded px-2 py-1.5 text-sm w-32 font-mono focus:outline-none focus:ring-2 focus:ring-amber-400 bg-white"
                            autoComplete="one-time-code"
                          />
                          <button
                            onClick={() => handleVerifyCode(a.id)}
                            disabled={verifyLoading === a.id || !verifyCode[a.id]}
                            className="bg-amber-500 hover:bg-amber-600 text-white px-3 py-1.5 rounded text-xs font-medium disabled:opacity-50 transition"
                          >
                            {verifyLoading === a.id ? "Submitting..." : "Submit OTP"}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Inline refresh-cookie panel for expired/login-required accounts */}
                    {refreshingId === a.id && (
                      <div className="mt-2 bg-blue-50 border border-blue-200 rounded-lg p-3">
                        <p className="text-xs font-semibold text-blue-800 mb-2">Paste a fresh session token to reconnect</p>
                        <div className="flex items-center gap-2 bg-slate-900 rounded px-2 py-1.5 mb-2">
                          <code className="text-green-400 text-xs flex-1 font-mono">{JS_SNIPPET}</code>
                          <button
                            type="button"
                            onClick={() => handleCopySnippetForRefresh(a.id)}
                            className="flex-shrink-0 bg-slate-700 hover:bg-slate-600 text-white text-xs px-2 py-1 rounded transition"
                          >
                            {refreshCopied[a.id] ? "Copied!" : "Copy"}
                          </button>
                        </div>
                        <p className="text-xs text-blue-600 mb-2">Run this in the LinkedIn browser console, then paste the result below</p>
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            placeholder="Paste token here..."
                            value={refreshValue[a.id] || ""}
                            onChange={(e) => setRefreshValue((prev) => ({ ...prev, [a.id]: e.target.value.trim() }))}
                            onKeyDown={(e) => e.key === "Enter" && handleRefreshCookies(a.id, a.email)}
                            className="border border-blue-300 rounded px-2 py-1.5 text-xs font-mono flex-1 focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white"
                          />
                          <button
                            onClick={() => handleRefreshCookies(a.id, a.email)}
                            disabled={refreshLoading === a.id || !refreshValue[a.id]}
                            className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded text-xs font-medium disabled:opacity-50 transition whitespace-nowrap"
                          >
                            {refreshLoading === a.id ? "Saving..." : "Reconnect"}
                          </button>
                          <button
                            onClick={() => setRefreshingId(null)}
                            className="text-slate-500 text-xs hover:text-slate-700"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-500">
                    {new Date(a.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      {(a.status === "login_required" || a.status === "inactive") && refreshingId !== a.id && (
                        <button
                          onClick={() => setRefreshingId(a.id)}
                          className="text-sm text-blue-600 hover:text-blue-700 font-medium"
                        >
                          Refresh Session
                        </button>
                      )}
                      {a.status === "active" && (
                        <button
                          onClick={() => setRefreshingId(refreshingId === a.id ? null : a.id)}
                          className="text-sm text-slate-500 hover:text-slate-700 font-medium"
                        >
                          {refreshingId === a.id ? "Cancel" : "Update Session"}
                        </button>
                      )}
                      {a.status === "login_required" && (
                        <button
                          onClick={() => handleLogin(a.id)}
                          disabled={loginLoading === a.id}
                          className="text-sm text-green-600 hover:text-green-700 font-medium disabled:opacity-50"
                        >
                          {loginLoading === a.id ? "Starting..." : "Login (password)"}
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(a.id)}
                        className="text-sm text-red-500 hover:text-red-600 font-medium"
                      >
                        Delete
                      </button>
                    </div>
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
