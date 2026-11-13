import type { Metadata } from "next";
import { Archivo } from "next/font/google";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import Shell from "@/components/Shell";

// Archivo carries a width axis: headings are set wide, like lettering on a spacecraft hull;
// text and numbers use the normal width of the same family.
const archivo = Archivo({ subsets: ["latin"], axes: ["wdth"], variable: "--font-archivo", display: "swap" });

export const metadata: Metadata = {
  title: "Freefall Atlas",
  description: "What NASA knows about fire in space, and what it does not: experiments, evidence and gaps in one place.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="void" className={`${archivo.variable} ${GeistMono.variable}`} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var s=JSON.parse(localStorage.getItem('freefall-atlas-2')||'{}');var t=(s.state||{}).theme;if(t)document.documentElement.dataset.theme=t;}catch(e){}`,
          }}
        />
      </head>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
