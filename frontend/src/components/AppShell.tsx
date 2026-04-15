"use client";

import { usePathname, useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import AuthGuard from "./AuthGuard";
import { clearToken } from "@/lib/api";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isLoginPage = pathname === "/login";

  const handleLogout = () => {
    clearToken();
    router.push("/login");
  };

  return (
    <AuthGuard>
      {isLoginPage ? (
        children
      ) : (
        <div className="flex min-h-full">
          <Sidebar />
          <main className="flex-1 ml-64 p-8">
            <div className="fixed top-4 right-6 z-40">
              <button
                onClick={handleLogout}
                className="text-xs text-slate-400 hover:text-slate-600 bg-white border border-slate-200 px-3 py-1.5 rounded-lg shadow-sm transition"
              >
                Logout
              </button>
            </div>
            {children}
          </main>
        </div>
      )}
    </AuthGuard>
  );
}
