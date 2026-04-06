import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SK Enmove MI Newsletter",
  description: "Global lubricant market intelligence newsletter management",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" className="dark">
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        <nav className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-red-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
                  SK
                </div>
                <span className="text-lg font-semibold">MI Newsletter</span>
              </div>
              <div className="flex items-center gap-6">
                <a href="/" className="text-gray-300 hover:text-white transition-colors text-sm">
                  Dashboard
                </a>
                <a href="/runs" className="text-gray-300 hover:text-white transition-colors text-sm">
                  Runs
                </a>
                <a href="/settings" className="text-gray-300 hover:text-white transition-colors text-sm">
                  Settings
                </a>
              </div>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
