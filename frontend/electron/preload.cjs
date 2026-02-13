const { contextBridge } = require("electron");

const runtimeArg = process.argv.find((arg) => arg.startsWith("--photonics-api-base="));
const apiBase = runtimeArg ? runtimeArg.replace("--photonics-api-base=", "") : "";

contextBridge.exposeInMainWorld("photonicsRuntime", {
  apiBase,
});
