import { fileURLToPath } from "node:url";

const [command, ...args] = process.argv.slice(2);
if (!["dev", "build"].includes(command)) throw new Error("Expected dev or build.");

process.env.BUYEROS_DEPLOY_TARGET = "vercel";
if (command === "build") process.env.NITRO_PRESET = "vercel";

const cli = new URL("../node_modules/vite/bin/vite.js", import.meta.url);
process.argv = [process.execPath, fileURLToPath(cli), command,
  ...(command === "dev" && process.env.PORT ? ["--port", process.env.PORT] : []),
  ...args];
await import(cli.href);
