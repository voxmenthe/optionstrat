import React from 'react';
import './globals.css';

export const metadata = {
  title: 'Options Analysis Tool',
  description: 'Advanced options scenario analysis and exploration tool',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        <header className="bg-gray-800 text-white p-4">
          <div className="container mx-auto flex justify-between items-center">
            <h1 className="text-xl font-bold">Options Analysis Tool</h1>
            <nav>
              <ul className="flex space-x-6">
                <li><a href="/" className="hover:text-gray-300">Home</a></li>
                <li><a href="/positions" className="hover:text-gray-300">Positions</a></li>
                <li><a href="/visualizations" className="hover:text-gray-300">Analysis</a></li>
                <li><a href="/market-data" className="hover:text-gray-300">Market Data</a></li>
              </ul>
            </nav>
          </div>
        </header>
        <main className="container mx-auto py-6 flex-grow">
          {children}
        </main>
        <footer className="bg-gray-100 border-t py-6">
          <div className="container mx-auto text-center text-gray-600">
            <p>Options Analysis Tool © 2024</p>
            <p className="text-sm mt-2">Disclaimer: This tool is for educational purposes only. Not financial advice.</p>
          </div>
        </footer>
      </body>
    </html>
  );
} 