#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import os from "node:os";
import path from "node:path";
const templateScript = path.join(os.homedir(), ".agent-template", "scripts", "lovable-sync.mjs");
const projectRoot = process.argv[2] || process.cwd();
const result = spawnSync(process.execPath, [templateScript, projectRoot], { stdio: "inherit" });
process.exit(result.status ?? 1);
