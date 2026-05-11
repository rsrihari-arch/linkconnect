"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

function isTokenValid(token: string): boolean {
  try {
    // Our JWT format: base64(payload).signature
    const [data] = token.split(".");
    const payload = JSON.parse(atob(data));
    return new Date(payload.exp) > new Date();
  } catch {
    return false;
  }
}

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    if (pathname === "/login") {
      setChecked(true);
      setAuthed(true);
      return;
    }

    const token = localStorage.getItem("token");
    if (!token || !isTokenValid(token)) {
      localStorage.removeItem("token");
      router.replace("/login");
      return;
    }

    // Token is valid — show content immediately without an API round-trip
    setAuthed(true);
    setChecked(true);
  }, [pathname, router]);

  if (!checked || !authed) {
    return (
      <div className="flex items-center justify-center h-screen text-slate-400">
        Loading...
      </div>
    );
  }

  return <>{children}</>;
}
