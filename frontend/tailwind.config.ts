import type { Config } from "tailwindcss";
const v = (n: string) => `var(--${n})`;
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: v("bg"), surface: v("surface"), "surface-2": v("surface-2"), "surface-3": v("surface-3"),
        line: v("line"), "line-strong": v("line-strong"), ink: v("text"), "ink-2": v("text-2"), "ink-3": v("text-3"),
        flame: v("flame"), ext: v("ext"), unc: v("unc"), nodata: v("nodata"), warn: v("warn"),
        prevention: v("prevention"), detection: v("detection"), suppression: v("suppression"),
      },
      fontFamily: { sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"], mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"] },
      borderRadius: { sm: "var(--r-sm)", DEFAULT: "var(--r-sm)", md: "var(--r-md)" },
      // nothing in the interface is set below 13 px
      fontSize: { "2xs": ["13px", "18px"], xs: ["13px", "18px"], sm: ["14px", "21px"], base: ["15px", "23px"], lg: ["18px", "26px"], xl: ["22px", "29px"] },
    },
  },
  plugins: [],
} satisfies Config;
