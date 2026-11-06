import { build, context } from "esbuild";
import { cpSync, mkdirSync, rmSync } from "node:fs";

rmSync("dist", { recursive: true, force: true });
mkdirSync("dist", { recursive: true });
cpSync("public", "dist", { recursive: true });

const options = {
  entryPoints: { app: "src/main.jsx" },
  bundle: true,
  minify: !process.argv.includes("--watch"),
  sourcemap: false,
  outdir: "dist",
  target: "es2020",
  jsx: "automatic",
  loader: { ".woff": "file" },
  external: ["/fonts/*"],
  define: { "process.env.NODE_ENV": '"production"' },
  logLevel: "info",
};

if (process.argv.includes("--watch")) {
  const ctx = await context(options);
  await ctx.watch();
} else {
  await build(options);
}
