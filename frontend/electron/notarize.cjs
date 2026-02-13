const path = require("path");
const { notarize } = require("@electron/notarize");

exports.default = async function notarizeApp(context) {
  if (process.platform !== "darwin" || context.electronPlatformName !== "darwin") {
    return;
  }

  const appleId = process.env.APPLE_ID;
  const appleIdPassword = process.env.APPLE_APP_SPECIFIC_PASSWORD;
  const teamId = process.env.APPLE_TEAM_ID;
  if (!appleId || !appleIdPassword || !teamId) {
    console.log("Skipping notarization: APPLE_ID / APPLE_APP_SPECIFIC_PASSWORD / APPLE_TEAM_ID not fully set.");
    return;
  }

  const appName = context.packager.appInfo.productFilename;
  await notarize({
    appPath: path.join(context.appOutDir, `${appName}.app`),
    appleId,
    appleIdPassword,
    teamId,
  });
};
