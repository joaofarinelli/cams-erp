import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { createSubscriber } from "./api";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export async function registerForPush(): Promise<string | null> {
  if (!Device.isDevice) {
    // Simulator/emulator can't get a real push token. Bail silently.
    return null;
  }

  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("alerts", {
      name: "Alertas",
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: "#06a",
    });
  }

  const existing = await Notifications.getPermissionsAsync();
  let status = existing.status;
  if (status !== "granted") {
    const req = await Notifications.requestPermissionsAsync();
    status = req.status;
  }
  if (status !== "granted") return null;

  const tokenResp = await Notifications.getExpoPushTokenAsync();
  const token = tokenResp.data;

  try {
    await createSubscriber("expo_push", token);
  } catch (e) {
    console.warn("registerForPush createSubscriber failed:", e);
  }
  return token;
}
