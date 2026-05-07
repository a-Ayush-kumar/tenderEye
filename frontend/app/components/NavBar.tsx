"use client";
import Link from "next/link";
import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";

export default function NavBar() {
  const pathname = usePathname();
  const [token, setToken] = useState<string | null>(null);
  const [userName, setUserName] = useState<string>("");

 useEffect(() => {
    const t = localStorage.getItem("vigil_token");
    const u = localStorage.getItem("vigil_user");
    setToken(t);
    if (u) {
      try {
        const parsed = JSON.parse(u);
        setUserName(parsed.name || "");
      } catch {
        setUserName("");
      }
    }
  }, [pathname]);

  function logout() {
    localStorage.removeItem("vigil_token");
    localStorage.removeItem("vigil_user");
    window.location.href = "/login";
  }

  const isLoginPage = pathname === "/login";

  return (
    <nav className="bg-primary-900 text-white px-6 py-4">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold">VIGIL</span>
          <span className="text-sm text-gray-300">| TenderEye Prototype</span>
        </div>

        {token && !isLoginPage ? (
          <div className="flex items-center gap-4 text-sm">
            <Link href="/" className="hover:text-gray-300 transition">Dashboard</Link>
            <Link href="/tenders" className="hover:text-gray-300 transition">Tenders</Link>
            <Link href="/vendors" className="hover:text-gray-300 transition">Vendors</Link>
            <Link href="/vigil" className="hover:text-gray-300 transition text-yellow-300">
              🛡️ VIGIL
            </Link>
            <Link
              href="/tenders/new"
              className="px-3 py-1 bg-primary-600 rounded-lg hover:bg-primary-500 transition font-medium"
            >
              + New Tender
            </Link>
            <div className="border-l border-gray-600 pl-4 flex items-center gap-2">
              <span className="text-gray-300">👤 {userName || "Officer"}</span>
              <button
                onClick={logout}
                className="text-xs text-red-300 hover:text-red-200 transition"
              >
                Logout
              </button>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-4 text-sm">
            {!isLoginPage && (
              <Link
                href="/login"
                className="px-3 py-1.5 bg-primary-600 rounded-lg hover:bg-primary-500 transition font-medium"
              >
                🔐 Officer Login
              </Link>
            )}
          </div>
        )}
      </div>
    </nav>
  );
}
