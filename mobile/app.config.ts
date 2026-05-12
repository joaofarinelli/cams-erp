import type { ExpoConfig } from "expo/config";

const apiBase = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

const config: ExpoConfig = {
  name: "cams-erp",
  slug: "cams-erp",
  version: "0.1.0",
  orientation: "portrait",
  userInterfaceStyle: "light",
  scheme: "camserp",
  ios: {
    supportsTablet: true,
    bundleIdentifier: "com.camserp.app",
  },
  android: {
    package: "com.camserp.app",
  },
  plugins: [
    "expo-router",
    [
      "expo-notifications",
      {
        color: "#06a",
      },
    ],
  ],
  extra: {
    apiBase,
    eas: {
      projectId: process.env.EAS_PROJECT_ID,
    },
  },
};

export default config;
